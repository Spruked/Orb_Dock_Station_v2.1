#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod desktop_host;
fn main() { desktop_host::run(desktop_host::Role::Station); }
