from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Tuple
from unittest.mock import MagicMock

import pytest

import pen.commands
from pen import AppConfig, Entry
from pen.commands import compose_command, import_journal, install_command


if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def test_compose_command(monkeypatch: "MonkeyPatch") -> None:
    input_str = "__blabla__"
    journal_name = "journal_name"

    def mock_parse_entry(_: AppConfig, entry_string: str) -> Entry:
        return Entry(datetime.now(), entry_string, "")

    config_mock = MagicMock()
    parse_entry_mock = MagicMock(side_effect=mock_parse_entry)
    open_editor_mock = MagicMock(side_effect=[input_str])
    from_name = MagicMock()
    monkeypatch.setattr(pen.commands, "open_editor", open_editor_mock)
    monkeypatch.setattr(pen.commands, "parse_entry", parse_entry_mock)
    monkeypatch.setattr(pen.commands.Journal, "from_name", from_name)

    compose_command(config_mock, Namespace(journal=journal_name))

    from_name.assert_called_once_with(journal_name, config_mock)
    open_editor_mock.assert_called_once_with(config_mock)
    parse_entry_mock.assert_called_once_with(config_mock, input_str)
    from_name.return_value.add.assert_called_once()


def test_compose_command__no_input(monkeypatch: "MonkeyPatch") -> None:
    input_str = ""
    journal_name = "journal_name"

    config_mock = MagicMock()
    open_editor_mock = MagicMock(side_effect=[input_str])
    from_name = MagicMock()
    monkeypatch.setattr(pen.commands, "open_editor", open_editor_mock)
    monkeypatch.setattr(pen.commands.Journal, "from_name", from_name)

    with pytest.raises(SystemExit):
        compose_command(config_mock, Namespace(journal=journal_name))


journals = ["jrnl_journal.txt", "pen_md_journal.md"]


@pytest.mark.parametrize("journal_name", journals)
def test_import_journal(
    journal_name: str,
    monkeypatch: "MonkeyPatch",
    datadir: Path,
    pen_dirs: Tuple[Path, Path],
    empty_config: AppConfig,
) -> None:
    journal_path = datadir / journal_name
    journal_dir = pen_dirs[0]
    empty_config.cli_args = Namespace(
        command="import", path=str(journal_path), move=True, keep=False
    )
    monkeypatch.setattr(
        pen.commands, "ask", lambda _, options, *__, **___: next(iter(options))
    )

    import_journal(empty_config, journal_path, new_file_type="pen-default-markdown")

    assert (journal_dir / journal_name).exists()


def test_install_command(
    monkeypatch: "MonkeyPatch", pen_dirs: Tuple[Path, Path], empty_config: AppConfig,
) -> None:
    journal_name = "default.md"
    journal_dir, config_path = pen_dirs
    empty_config.cli_args = Namespace(command="compose")

    ask_answers = iter((str(journal_dir), journal_name))
    monkeypatch.setattr(pen.commands, "ask", lambda *_, **__: next(ask_answers))
    monkeypatch.setattr("builtins.input", lambda *_: None)
    monkeypatch.setattr(pen.commands, "yes_no", lambda *_, **__: False)

    install_command(empty_config)

    assert config_path.exists()
