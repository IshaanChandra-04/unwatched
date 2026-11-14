from unwatched.schedule import TASK_NAME, build_register_script


def test_register_script_has_required_settings_and_quotes_spaces():
    s = build_register_script(
        r"C:\Program Files\unwatched\unwatched.exe",
        r"C:\Users\me\My Config\unwatched.toml",
        "15:00",
    )
    assert TASK_NAME == "unwatched daily"
    assert f"-TaskName '{TASK_NAME}'" in s
    assert "-Daily -At '15:00'" in s
    assert "-StartWhenAvailable" in s and "-WakeToRun" in s
    assert "-LogonType Interactive" in s and "-Priority 7" in s and "-Hours 2" in s
    assert "-Execute 'C:\\Program Files\\unwatched\\unwatched.exe'" in s
    assert "-Argument 'run --config \"C:\\Users\\me\\My Config\\unwatched.toml\"'" in s


def test_register_script_escapes_single_quotes_in_paths():
    s = build_register_script(
        r"C:\Users\O'Brien\unwatched.exe", r"C:\Users\O'Brien\u.toml", "09:30"
    )
    assert "-Execute 'C:\\Users\\O''Brien\\unwatched.exe'" in s
    assert "-Argument 'run --config \"C:\\Users\\O''Brien\\u.toml\"'" in s
