import ast
from pathlib import Path

import pytest
from pylsp import uris
from rope.base.exceptions import RefactoringError

from pylsp_rope import commands, plugin
from pylsp_rope.refactoring import CommandRefactorMove
from pylsp_rope.text import Range
from test.conftest import create_document
from test.helpers import assert_is_apply_edit_request


def write_module(workspace, name, source):
    path = Path(workspace.root_path) / name
    path.write_text(source)
    return workspace.get_document(uris.from_fs_path(str(path)))


def move_actions(config, workspace, document, selection, context):
    return [
        action
        for action in plugin.pylsp_code_actions(
            config, workspace, document, selection, context
        )
        if action["command"]["command"] == commands.COMMAND_REFACTOR_MOVE
    ]


def apply_text_edits(document, edits):
    source = document.source
    for edit in sorted(
        edits,
        key=lambda edit: document.offset_at_position(edit["range"]["start"]),
        reverse=True,
    ):
        start = document.offset_at_position(edit["range"]["start"])
        end = document.offset_at_position(edit["range"]["end"])
        source = source[:start] + edit["newText"] + source[end:]
    return source


@pytest.mark.parametrize(
    "name,line", [("TestClass", 0), ("standalone_function", 6), ("class_to_move", 11)]
)
def test_move_global(config, workspace, code_action_context, name, line):
    document = create_document(workspace, "move_test.py")
    destination = write_module(workspace, "destination.py", "# Destination\n")
    consumer = write_module(
        workspace, "consumer.py", f"from move_test import {name}\nvalue = {name}\n"
    )
    character = document.lines[line].index(name)
    selection = Range((line, character), (line, character))
    actions = move_actions(
        config, workspace, document, selection, code_action_context
    )
    action = next(a for a in actions if a["title"] == "Move to destination.py")
    assert all(a["title"] != "Move to move_test.py" for a in actions)
    command = action["command"]
    assert command["arguments"][0]["destination"] == "destination.py"

    plugin.pylsp_execute_command(
        config, workspace, command["command"], command["arguments"]
    )

    edit = assert_is_apply_edit_request(workspace._endpoint.request.call_args)
    assert set(edit["changes"]) == {document.uri, destination.uri, consumer.uri}
    updated = {
        doc.uri: apply_text_edits(doc, edit["changes"][doc.uri])
        for doc in (document, destination, consumer)
    }
    source_tree = ast.parse(updated[document.uri])
    dest_tree = ast.parse(updated[destination.uri])

    def defines(tree, symbol):
        return any(
            getattr(node, "name", None) == symbol
            or isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == symbol for t in node.targets)
            for node in tree.body
        )

    assert not defines(source_tree, name)
    assert defines(dest_tree, name)
    assert updated[consumer.uri] == (
        f"import destination\nvalue = destination.{name}\n"
    )
    for source in updated.values():
        ast.parse(source)
    workspace._endpoint.notify.assert_not_called()


@pytest.mark.parametrize("position", [(1, 8), (2, 8), (8, 0)])
def test_no_move_for_method_local_or_blank(
    config, workspace, code_action_context, position
):
    document = create_document(workspace, "move_test.py")
    write_module(workspace, "destination.py", "")
    assert not move_actions(
        config, workspace, document, Range(position, position), code_action_context
    )


def test_no_move_for_module(config, workspace, code_action_context):
    document = write_module(workspace, "source.py", "import destination\n")
    write_module(workspace, "destination.py", "")
    selection = Range((0, 7), (0, 7))
    assert not move_actions(
        config, workspace, document, selection, code_action_context
    )


def test_no_move_to_conflicting_or_source_module(
    config, workspace, code_action_context
):
    document = create_document(workspace, "move_test.py")
    write_module(workspace, "destination.py", "TestClass = None\n")
    selection = Range((0, 6), (0, 6))
    assert not move_actions(
        config, workspace, document, selection, code_action_context
    )


def test_destination_conflict_rechecked_on_execution(config, workspace):
    document = create_document(workspace, "move_test.py")
    write_module(workspace, "destination.py", "TestClass = None\n")
    plugin.pylsp_execute_command(
        config,
        workspace,
        commands.COMMAND_REFACTOR_MOVE,
        [{
            "document_uri": document.uri,
            "position": {"line": 0, "character": 6},
            "destination": "destination.py",
        }],
    )
    workspace._endpoint.request.assert_not_called()
    workspace._endpoint.notify.assert_called_once()
    assert "Destination already defines" in str(
        workspace._endpoint.notify.call_args
    )


@pytest.mark.parametrize(
    "destination", ["missing.py", "move_test.py", "../outside.py", "/tmp/outside.py"]
)
def test_invalid_destination_rejected(workspace, destination):
    document = create_document(workspace, "move_test.py")
    command = CommandRefactorMove(
        workspace,
        document_uri=document.uri,
        position={"line": 0, "character": 6},
        destination=destination,
    )
    with pytest.raises(RefactoringError):
        command.get_changes()
    workspace._endpoint.request.assert_not_called()
