"""
test_file_tools.py — Unit tests for file and folder management tools.
"""

import os
import shutil
import tempfile
import pytest

from agent_tools import file_tools
from agent_tools.executor import execute_tool


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    if os.path.exists(d):
        shutil.rmtree(d, ignore_errors=True)


def test_create_folder(temp_dir):
    folder_name = "test_subfolder"
    res = file_tools.create_folder(folder_name=folder_name, parent_dir=temp_dir)
    assert res["success"] is True
    expected_path = os.path.join(temp_dir, folder_name)
    assert os.path.exists(expected_path)
    assert os.path.isdir(expected_path)


def test_create_file(temp_dir):
    filename = "sample.txt"
    content = "Hello Kairos test content!"
    res = file_tools.create_file(filename=filename, content=content, parent_dir=temp_dir)
    assert res["success"] is True
    expected_path = os.path.join(temp_dir, filename)
    assert os.path.exists(expected_path)
    with open(expected_path, "r", encoding="utf-8") as f:
        read_content = f.read()
    assert read_content == content


def test_rename_folder(temp_dir):
    old_folder = os.path.join(temp_dir, "old_dir")
    os.makedirs(old_folder, exist_ok=True)
    
    res = file_tools.rename_file_or_folder(old_name="old_dir", new_name="new_dir", parent_dir=temp_dir)
    assert res["success"] is True
    assert not os.path.exists(old_folder)
    assert os.path.exists(os.path.join(temp_dir, "new_dir"))


def test_list_directory_contents(temp_dir):
    os.makedirs(os.path.join(temp_dir, "dir1"), exist_ok=True)
    with open(os.path.join(temp_dir, "file1.txt"), "w") as f:
        f.write("test")

    res = file_tools.list_directory_contents(path=temp_dir)
    assert res["success"] is True
    assert "dir1" in res["folders"]
    assert "file1.txt" in res["files"]


def test_execute_tool_file_tools(temp_dir):
    # Test dispatch via execute_tool
    res_folder = execute_tool("create_folder", {"folder_name": "exec_dir", "parent_dir": temp_dir})
    assert res_folder["success"] is True
    assert os.path.exists(os.path.join(temp_dir, "exec_dir"))

    res_file = execute_tool("create_file", {"filename": "exec_file.txt", "content": "exec text", "parent_dir": temp_dir})
    assert res_file["success"] is True
    assert os.path.exists(os.path.join(temp_dir, "exec_file.txt"))

    res_rename = execute_tool("rename_file_or_folder", {"old_name": "exec_file.txt", "new_name": "renamed_file.txt", "parent_dir": temp_dir})
    assert res_rename["success"] is True
    assert os.path.exists(os.path.join(temp_dir, "renamed_file.txt"))


def test_execute_open_cmd_mkdir_and_touch(temp_dir, monkeypatch):
    monkeypatch.setattr(file_tools, "get_desktop_dir", lambda: temp_dir)

    res_mkdir = execute_tool("open_cmd", {"command": f'mkdir "{temp_dir}\\Ram"'})
    assert res_mkdir["success"] is True
    ram_folder = os.path.join(temp_dir, "Ram")
    assert os.path.exists(ram_folder)

    res_touch = execute_tool("open_cmd", {"command": f'touch "{temp_dir}\\Ram\\Rani"'})
    assert res_touch["success"] is True
    rani_file = os.path.join(ram_folder, "Rani")
    assert os.path.exists(rani_file)
