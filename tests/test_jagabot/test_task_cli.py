"""Tests for jagabot.cli.task_commands — task board CLI."""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from jagabot.cli.task_commands import task_app, DEFAULT_TASKS_DIR


runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_tasks_dir(tmp_path):
    with patch("jagabot.cli.task_commands.DEFAULT_TASKS_DIR", tmp_path / "tasks"):
        yield


class TestTaskCreate:
    def test_create_basic(self):
        result = runner.invoke(task_app, ["create", "Build API"])
        assert result.exit_code == 0
        assert "Created task" in result.output

    def test_create_with_desc(self):
        result = runner.invoke(task_app, ["create", "Build API", "--desc", "REST endpoints"])
        assert result.exit_code == 0


class TestTaskList:
    def test_list_empty(self):
        result = runner.invoke(task_app, ["list"])
        assert result.exit_code == 0
        assert "No tasks" in result.output

    def test_list_after_create(self):
        runner.invoke(task_app, ["create", "Build API"])
        result = runner.invoke(task_app, ["list"])
        assert result.exit_code == 0
        assert "Build API" in result.output

    def test_list_ready(self):
        runner.invoke(task_app, ["create", "Build API"])
        result = runner.invoke(task_app, ["list", "--ready"])
        assert result.exit_code == 0


class TestTaskGet:
    def test_get_existing(self):
        runner.invoke(task_app, ["create", "Build API"])
        result = runner.invoke(task_app, ["get", "1"])
        assert result.exit_code == 0
        assert "Build API" in result.output

    def test_get_nonexistent(self):
        result = runner.invoke(task_app, ["get", "999"])
        assert result.exit_code == 1

    def test_get_json(self):
        runner.invoke(task_app, ["create", "Build API"])
        result = runner.invoke(task_app, ["get", "1", "--json"])
        assert result.exit_code == 0
        assert '"subject"' in result.output


class TestTaskUpdate:
    def test_update_status(self):
        runner.invoke(task_app, ["create", "Build API"])
        result = runner.invoke(task_app, ["update", "1", "--status", "in_progress"])
        assert result.exit_code == 0
        assert "Updated" in result.output

    def test_update_invalid_status(self):
        runner.invoke(task_app, ["create", "Build API"])
        result = runner.invoke(task_app, ["update", "1", "--status", "bogus"])
        assert result.exit_code == 1


class TestTaskRender:
    def test_render_empty(self):
        result = runner.invoke(task_app, ["render"])
        assert result.exit_code == 0
        assert "No tasks" in result.output

    def test_render_with_tasks(self):
        runner.invoke(task_app, ["create", "Build API"])
        result = runner.invoke(task_app, ["render"])
        assert result.exit_code == 0
        assert "#1" in result.output
