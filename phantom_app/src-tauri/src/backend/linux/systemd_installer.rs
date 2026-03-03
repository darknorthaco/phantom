use std::path::Path;

const UNIT_TEMPLATE: &str = r#"[Unit]
Description=Phantom Distributed Compute Controller
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={working_dir}
ExecStart={python} {run_py} --host 127.0.0.1 --port 8080 --security basic
Environment=PHANTOM_STATE_DIR={state_dir}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"#;

pub fn generate_unit_file(
    user: &str,
    python_path: &Path,
    run_py: &Path,
    working_dir: &Path,
    state_dir: &Path,
) -> String {
    UNIT_TEMPLATE
        .replace("{user}", user)
        .replace("{python}", &python_path.to_string_lossy())
        .replace("{run_py}", &run_py.to_string_lossy())
        .replace("{working_dir}", &working_dir.to_string_lossy())
        .replace("{state_dir}", &state_dir.to_string_lossy())
}
