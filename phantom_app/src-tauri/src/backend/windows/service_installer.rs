pub fn generate_service_config(
    _service_name: &str,
    _python_path: &str,
    _run_py: &str,
) -> String {
    String::from("Windows service installation is handled via sc.exe or NSSM")
}
