use std::{path::PathBuf, process::{Child,Command}, sync::Mutex, time::{Duration,SystemTime,UNIX_EPOCH}};
use tauri::{Emitter,Manager,menu::{Menu,MenuItem},tray::TrayIconBuilder};
#[cfg(windows)] use std::os::windows::process::CommandExt;

pub enum Role { Station }
struct Lifecycle { launch_id:String, root:PathBuf, report:PathBuf, child:Mutex<Option<Child>> }
impl Lifecycle {
    fn token(&self)->Result<String,String> {
        let path=std::env::var_os("ORBOT_VAULT_TOKEN_FILE").map(PathBuf::from).unwrap_or_else(||self.root.parent().unwrap().join("Orbot/Orbot_Vault-Logic-System/.local/host-memory.token"));
        std::fs::read_to_string(path).map(|token|token.trim().to_owned()).map_err(|_|"Existing Vault credential unavailable".into())
    }
    fn status(&self)->serde_json::Value {
        let value=std::fs::read(&self.report).ok().and_then(|bytes|serde_json::from_slice::<serde_json::Value>(&bytes).ok());
        if let Ok(mut holder)=self.child.lock() {
            if let Some(child)=holder.as_mut() {
                if matches!(child.try_wait(),Ok(Some(_))) && value.as_ref().is_some_and(|v|v["ready"]==true) {
                    return serde_json::json!({"launch_id":self.launch_id,"phase":"failed","ready":false,"error":"Lifecycle coordinator exited; startup reconciliation is required"});
                }
            }
        }
        match value {
            Some(value) if value["launch_id"]==self.launch_id=>value,
            _=>serde_json::json!({"launch_id":self.launch_id,"phase":"starting","ready":false})
        }
    }
    fn start(&self)->Result<(),String> {
        let mut holder=self.child.lock().map_err(|e|e.to_string())?;
        if let Some(child)=holder.as_mut() {
            if child.try_wait().map_err(|e|e.to_string())?.is_none() {return Ok(());}
        }
        std::fs::create_dir_all(self.report.parent().unwrap()).map_err(|e|e.to_string())?;
        std::fs::write(&self.report,serde_json::json!({"launch_id":self.launch_id,"phase":"starting","ready":false}).to_string()).map_err(|e|e.to_string())?;
        let mut command=Command::new(self.root.join("backend/.venv/Scripts/python.exe"));
        command.arg("-B").arg(self.root.join("backend/desktop_lifecycle.py"))
            .arg("--launch-id").arg(&self.launch_id).arg("--report").arg(&self.report).current_dir(&self.root);
        #[cfg(windows)] command.creation_flags(0x08000000);
        *holder=Some(command.spawn().map_err(|e|e.to_string())?);
        Ok(())
    }
}
fn peer(path:&str,post:bool,state:&Lifecycle)->Result<String,String> {
    let client=reqwest::blocking::Client::builder().timeout(Duration::from_secs(10)).no_proxy().build().map_err(|e|e.to_string())?;
    let url=format!("http://127.0.0.1:16523{path}");
    let req=if post {client.post(url)} else {client.get(url)};
    let req=if post {req.bearer_auth(state.token()?)} else {req};
    let response=req.header("X-Orbot-Desktop","1").header("X-Orbot-Launch",&state.launch_id).send().map_err(|e|e.to_string())?;
    let status=response.status();let body=response.text().map_err(|e|e.to_string())?;
    if !status.is_success() {return Err(body);}
    Ok(body)
}
fn release(state:&Lifecycle)->Result<String,String> {
    if state.status()["ready"]!=true {return Err("Orbot initialization is not ready; it remains docked".into());}
    peer("/undock",true,state)
}
#[tauri::command]
async fn peer_status(app:tauri::AppHandle)->Result<String,String> {
    tauri::async_runtime::spawn_blocking(move ||peer("/status",false,&app.state::<Lifecycle>())).await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn dock_orbot(app:tauri::AppHandle)->Result<String,String> {
    tauri::async_runtime::spawn_blocking(move ||peer("/dock",true,&app.state::<Lifecycle>())).await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn undock_orbot(app:tauri::AppHandle)->Result<String,String> {
    tauri::async_runtime::spawn_blocking(move ||release(&app.state::<Lifecycle>())).await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn voice_status() -> Result<serde_json::Value,String> {
    tauri::async_runtime::spawn_blocking(||{
        reqwest::blocking::Client::builder().timeout(Duration::from_secs(3)).no_proxy().build().map_err(|e|e.to_string())?
            .get("http://127.0.0.1:16521/diagnostics").send().and_then(|r|r.error_for_status()).and_then(|r|r.json::<serde_json::Value>())
            .map(|value|value["metrics"].as_object().map(|metrics|metrics.iter().filter(|(key,_)|key.starts_with("voice.")).map(|(key,value)|(key.clone(),value.clone())).collect::<serde_json::Map<_,_>>()).map(serde_json::Value::Object).unwrap_or(serde_json::Value::Null)).map_err(|e|e.to_string())
    }).await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn voice_control(app:tauri::AppHandle, action:String)->Result<String,String> {
    if !matches!(action.as_str(),"start"|"pause"|"cancel"|"refresh_devices") {return Err("Unknown voice control".into());}
    tauri::async_runtime::spawn_blocking(move ||peer(&format!("/voice/{action}"),true,&app.state::<Lifecycle>())).await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn set_microphone(app:tauri::AppHandle, device_id:String, label:String)->Result<(),String> {
    tauri::async_runtime::spawn_blocking(move ||{
        let state=app.state::<Lifecycle>();
        reqwest::blocking::Client::builder().timeout(Duration::from_secs(8)).no_proxy().build().map_err(|e|e.to_string())?
            .post("http://127.0.0.1:16523/voice/input-device").bearer_auth(state.token()?)
            .header("X-Orbot-Desktop","1").header("X-Orbot-Launch",&state.launch_id)
            .json(&serde_json::json!({"device_id":device_id,"label":label})).send().and_then(|r|r.error_for_status()).map(|_|()).map_err(|e|e.to_string())
    }).await.map_err(|e|e.to_string())?
}
#[tauri::command]
fn startup_status(app:tauri::AppHandle)->serde_json::Value {app.state::<Lifecycle>().status()}
#[tauri::command]
fn retry_startup(app:tauri::AppHandle)->Result<(),String> {app.state::<Lifecycle>().start()}

pub fn run(_role:Role) {
    let root=std::env::var_os("ORBOT_DOCK_ROOT").map(PathBuf::from).unwrap_or_else(||PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().parent().unwrap().to_path_buf());
    let launch_id=format!("{}-{}",std::process::id(),SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos());
    let report=root.join(".local").join(format!("lifecycle-{launch_id}.json"));
    tauri::Builder::default().manage(Lifecycle{launch_id:launch_id.clone(),root,report,child:Mutex::new(None)})
        .invoke_handler(tauri::generate_handler![peer_status,dock_orbot,undock_orbot,startup_status,retry_startup,voice_status,voice_control,set_microphone])
        .setup(move |app| {
            let show=MenuItem::with_id(app,"show","Show Dock Station",true,None::<&str>)?;
            let release_item=MenuItem::with_id(app,"release","Launch Orbot",true,None::<&str>)?;
            let recall=MenuItem::with_id(app,"recall","Recall Orbot",true,None::<&str>)?;
            let quit=MenuItem::with_id(app,"quit","Quit Dock and owned Orbot processes",true,None::<&str>)?;
            let menu=Menu::with_items(app,&[&show,&release_item,&recall,&quit])?;
            TrayIconBuilder::new().icon(tauri::image::Image::from_bytes(include_bytes!("orbot.png"))?).tooltip("Orbot Dock Station")
                .menu(&menu).on_menu_event(|app,event|match event.id.as_ref() {
                    "quit"=>app.exit(0),
                    "show"=>{if let Some(w)=app.get_webview_window("station"){let _=w.show();let _=w.set_focus();}},
                    "release"=>{let handle=app.clone();std::thread::spawn(move ||{let _=release(&handle.state::<Lifecycle>());});},
                    "recall"=>{let handle=app.clone();std::thread::spawn(move ||{let _=peer("/dock",true,&handle.state::<Lifecycle>());});}, _=>{}
                }).build(app)?;
            let server=tiny_http::Server::http(("127.0.0.1",16522)).map_err(|e|std::io::Error::other(e.to_string()))?;
            let handle=app.handle().clone();let owner=launch_id.clone();
            // Requests must be concurrent: release checks call back to Dock status.
            std::thread::spawn(move ||for req in server.incoming_requests() {
                let app=handle.clone();let owner=owner.clone();
                std::thread::spawn(move || {
                    let header=req.headers().iter().any(|h|h.field.equiv("X-Orbot-Desktop")&&h.value.as_str()=="1");
                    let launch=req.headers().iter().any(|h|h.field.equiv("X-Orbot-Launch")&&h.value.as_str()==owner);
                    let status_read=req.url()=="/status"&&req.method()==&tiny_http::Method::Get;
                    if !header||(!status_read&&!launch){let _=req.respond(tiny_http::Response::empty(403));return;}
                    let post=req.method()==&tiny_http::Method::Post;
                    let state=app.state::<Lifecycle>();
                    if post {
                        let authorized=state.token().ok().is_some_and(|token|req.headers().iter().any(|h|h.field.equiv("Authorization")&&h.value.as_str()==format!("Bearer {token}")));
                        if !authorized {let _=req.respond(tiny_http::Response::empty(401));return;}
                    }
                    let mut shutdown=false;
                    let result:Result<(),String>=match(req.url(),post){
                        ("/status",false)=>Ok(()),
                        ("/show",true)=>{
                            let _=app.emit("orbot:show-docking-bay",());
                            app.get_webview_window("station").ok_or("Station unavailable".into()).and_then(|w|w.show().and_then(|_|w.set_focus()).map_err(|e|e.to_string()))
                        },
                        ("/release",true)=>release(&state).map(|_|()),
                        ("/dock",true)=>peer("/dock",true,&state).map(|_|()),
                        ("/shutdown",true)=>{shutdown=true;Ok(())},
                        _=>Err("Unknown lifecycle operation".into())
                    };
                    let response=match result{
                        Ok(())=>tiny_http::Response::from_string(serde_json::json!({"application":"station","launch_id":owner,"lifecycle":state.status()}).to_string()),
                        Err(error)=>tiny_http::Response::from_string(serde_json::json!({"error":error}).to_string()).with_status_code(503)
                    };
                    let _=req.respond(response);
                    if shutdown{app.exit(0);}
                });
            });
            if let Err(error)=app.state::<Lifecycle>().start(){
                let state=app.state::<Lifecycle>();
                let _=std::fs::write(&state.report,serde_json::json!({"launch_id":state.launch_id,"phase":"failed","ready":false,"error":error}).to_string());
            }
            Ok(())
        })
        .on_window_event(|window,event|if let tauri::WindowEvent::CloseRequested{api,..}=event{api.prevent_close();let _=window.hide();})
        .run(tauri::generate_context!()).expect("Unable to run Dock Station");
}
