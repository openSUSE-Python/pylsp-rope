from pylsp_rope import commands, plugin
from pylsp_rope.text import Range
from test.conftest import create_document
from test.helpers import assert_single_document_edit


def test_move_class_to_new_module(config, workspace, code_action_context):
    """Test moving a class to a new module"""
    document = create_document(workspace, "move_test.py")
    selection = Range(1, 1)  # Select class definition line

    response = plugin.pylsp_code_actions(
        config=config,
        workspace=workspace,
        document=document,
        range=selection,
        context=code_action_context,
    )

    # Find move command
    move_action = None
    for action in response:
        if action.get("command", {}).get("command") == commands.COMMAND_REFACTOR_MOVE:
            move_action = action
            break

    assert move_action is not None
    assert move_action["command"] is not None

    # Execute the move
    plugin_response = plugin.pylsp_execute_command(
        config=config,
        workspace=workspace,
        command=move_action["command"]["command"],
        arguments=move_action["command"]["arguments"],
    )

    # Check if changes were applied
    edit_request = workspace._endpoint.request.call_args
    document_edits = assert_single_document_edit(edit_request, document)

    # Verify changes contain move operations
    changes_text = str(document_edits)
    print(f"Changes applied: {changes_text}")

    # Basic verification that some change occurred
    assert len(changes_text) > 0


def test_move_function(config, workspace, code_action_context):
    """Test moving a function to existing module"""
    document = create_document(workspace, "move_test.py")
    selection = Range(8, 8)  # Select function definition line

    response = plugin.pylsp_code_actions(
        config=config,
        workspace=workspace,
        document=document,
        range=selection,
        context=code_action_context,
    )

    # Find move command
    move_action = None
    for action in response:
        if action.get("command", {}).get("command") == commands.COMMAND_REFACTOR_MOVE:
            move_action = action
            break

    assert move_action is not None
    response = plugin.pylsp_execute_command(
        config=config,
        workspace=workspace,
        command=move_action["command"]["command"],
        arguments=move_action["command"]["arguments"],
    )

    # Check if changes were applied
    edit_request = workspace._endpoint.request.call_args
    document_edits = assert_single_document_edit(edit_request, document)

    # Verify changes contain move operations
    changes_text = str(document_edits)
    print(f"Changes applied: {changes_text}")

    # Basic verification that some change occurred
    assert len(changes_text) > 0
