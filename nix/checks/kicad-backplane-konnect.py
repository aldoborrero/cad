"""Check Konnect MCP against the headless server using disposable fixtures."""

import json
from collections import Counter
from pathlib import Path
import selectors
import subprocess
import sys


def main():
    cli, konnect, source = sys.argv[1:]
    sys.path.insert(0, str(Path(source).resolve() / "scripts"))
    from backplane_ipc_test_support import IpcSession

    with IpcSession(cli) as session:
        project = session.module("common.commands.project_commands")
        types = session.module("common.types.base_types")
        design = session.copy_project("demos/ecc83", "konnect")
        board = design / "ecc83-pp.kicad_pcb"

        def open_board():
            return session.request(
                project.OpenDocument(type=types.DOCTYPE_PCB, path=str(board)),
                project.OpenDocumentResponse,
            ).document

        document = open_board()
        env = session.env | {
            "KICAD_API_SOCKET": f"ipc://{session.socket}",
            "KONNECT_STATE_DIR": str(session.root / "konnect-state"),
        }
        with subprocess.Popen(
            [konnect],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=env,
            cwd=design,
        ) as process:
            sequence = 0
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)

                def rpc(method, params):
                    nonlocal sequence
                    sequence += 1
                    process.stdin.write(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "id": sequence,
                                "method": method,
                                "params": params,
                            }
                        )
                        + "\n"
                    )
                    process.stdin.flush()
                    while True:
                        assert selector.select(timeout=60), f"MCP timeout: {method}"
                        line = process.stdout.readline()
                        assert line, f"MCP exited: {process.poll()}"
                        result = json.loads(line)
                        if result.get("id") == sequence:
                            assert "error" not in result, result
                            return result["result"]

                def call(tool_name, **arguments):
                    result = rpc(
                        "tools/call", {"name": tool_name, "arguments": arguments}
                    )
                    assert not result.get("isError"), result
                    text = result["content"][0]["text"]
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text

                try:
                    rpc(
                        "initialize",
                        {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "nix-ipc-check", "version": "1"},
                        },
                    )
                    process.stdin.write(
                        '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
                    )
                    process.stdin.flush()
                    call("list_toolboxes")
                    for toolset in ["pcb_board", "pcb_routing", "project"]:
                        call("load_toolset", name=toolset)
                    # query_traces uses IPC in both Konnect 0.2.2 and 0.11.0.
                    before = call("query_traces", board=str(board))
                    assert before["count"] > 0, before
                    nets = call("get_nets_list", board=str(board))["nets"]
                    net = next(n["name"] for n in nets if n["name"])
                    call(
                        "route_trace",
                        board=str(board),
                        net_name=net,
                        layer="F.Cu",
                        width=0.25,
                        x1=10,
                        y1=10,
                        x2=20,
                        y2=10,
                    )
                    after = call("query_traces", board=str(board))
                    assert after["count"] == before["count"] + 1, (before, after)
                    call("save_project")
                    from google.protobuf.empty_pb2 import Empty

                    session.request(project.CloseDocument(document=document), Empty)
                    open_board()
                    reopened = call("query_traces", board=str(board))
                    # Item enumeration order may change when the native file is parsed.
                    expected = Counter(
                        json.dumps(t, sort_keys=True) for t in after["traces"]
                    )
                    actual = Counter(
                        json.dumps(t, sort_keys=True) for t in reopened["traces"]
                    )
                    assert reopened["count"] == after["count"] and actual == expected, (
                        after,
                        reopened,
                    )
                    print(
                        "PASS Konnect: live IPC traces, route creation, save and reopen"
                    )
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == "__main__":
    main()
