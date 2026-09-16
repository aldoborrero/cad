# Exercise the fork's real headless IPC implementation and saved-file behavior.
# Upstream tests copy their own fixtures and remove DISPLAY/WAYLAND_DISPLAY.
{
  pkgs,
  inputs,
  perSystem,
  ...
}:
let
  python = pkgs.python3.withPackages (ps: [
    ps.protobuf5
    ps.pynng
  ]);
in
pkgs.runCommand "kicad-backplane-ipc-check"
  {
    nativeBuildInputs = [
      python
      pkgs.protobuf_29
      pkgs.writableTmpDirAsHomeHook
    ];
  }
  ''
    mkdir -p $out
    # copytree preserves mode bits: fixtures copied directly from the store
    # remain read-only, preventing the save/reopen tests from saving them.
    cp -r ${inputs.kicad-backplane} source
    chmod -R u+w source
    cli=${perSystem.self.kicad-backplane}/bin/kicad-cli
    "$cli" api-server --help > $out/api-server-help.txt
    PYTHONPATH=${perSystem.self.kicad-backplane.base}/${pkgs.python3.sitePackages} \
      python - <<'PY' > $out/uuid.log
    import pcbnew
    import threading
    def check():
        random_ids = [pcbnew.KIID("").AsString() for _ in range(100)]
        assert len(set(random_ids)) == 100
        pcbnew.KIID.SeedGenerator(42)
        first = [pcbnew.KIID().AsString() for _ in range(100)]
        pcbnew.KIID.SeedGenerator(42)
        assert first == [pcbnew.KIID().AsString() for _ in range(100)]
        assert len(set(first)) == 100
    check()
    errors = []
    def thread_check():
        try:
            check()
        except BaseException as error:
            errors.append(error)
    thread = threading.Thread(target=thread_check)
    thread.start()
    thread.join()
    assert not errors, errors
    print("PASS UUID generation and deterministic QA seeding on two threads")
    PY
    # Cold starts matter: the initial UUID collision was intermittent.
    for attempt in {1..10}; do
      python source/scripts/backplane-ipc-smoke.py "$cli" \
        > "$out/smoke-$attempt.log" 2>&1 || { cat "$out/smoke-$attempt.log"; exit 1; }
    done
    python source/scripts/backplane-ipc-rulecheck-regression.py "$cli" \
      > $out/rulecheck.log 2>&1 || { cat $out/rulecheck.log; exit 1; }
    python ${./kicad-backplane-konnect.py} "$cli" ${perSystem.self.konnect}/bin/konnect source \
      > $out/konnect.log 2>&1 || { cat $out/konnect.log; exit 1; }
    cat $out/uuid.log $out/smoke-*.log $out/rulecheck.log $out/konnect.log
  ''
