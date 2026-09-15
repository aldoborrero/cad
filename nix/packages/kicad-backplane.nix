# Reuse nixpkgs' native build, Nix runtime patches and complete KiCad wrapper.
# The stable package ignores `srcs`, so override the arguments passed to base.nix.
# Keep the existing library packages and stock KiCad available independently.
{ pkgs, inputs, ... }:
let
  inherit (pkgs) lib;
  version = "10.0.6-backplane-${builtins.substring 0 12 inputs.kicad-backplane.rev}";
  runtime = pkgs.kicad.override {
    pname = "kicad-backplane";
    callPackage =
      path: args:
      if builtins.baseNameOf path == "base.nix" then
        (pkgs.callPackage path (
          args
          // {
            kicadSrc = inputs.kicad-backplane;
            kicadVersion = version;
          }
        )).overrideAttrs
          (old: {
            pname = "kicad-backplane-base";
            # Bypass libstdc++'s direct RDSEED default for UUID entropy: the host
            # reproduced AMD-SB-7055-like zero output. Keep the OS RNG instead.
            patches = old.patches ++ [ ./kicad-backplane-os-entropy.patch ];
            cmakeFlags = old.cmakeFlags ++ [ (lib.cmakeBool "KICAD_IPC_API" true) ];
            postInstall = (old.postInstall or "") + ''
              mkdir -p $out/share/doc/kicad-backplane
              cp "$src"/LICENSE* "$src/AUTHORS.txt" "$src/BACKPLANE_IPC.md" \
                $out/share/doc/kicad-backplane/
            '';
          })
      else
        pkgs.callPackage path args;
  };
in
runtime.overrideAttrs (old: {
  inherit version;
  # The source was already overridden inside the native base derivation above.
  __intentionallyOverridingVersion = true;
  postInstall = old.postInstall + ''
    mkdir -p $out/share/doc
    ln -s ${old.base}/share/doc/kicad-backplane $out/share/doc/kicad-backplane
  '';
  meta = old.meta // {
    description = "KiCad 10.0.6 with Backplane headless PCB and schematic IPC backports";
    homepage = "https://github.com/i2cjak/Backplane_KiCad";
    mainProgram = "kicad-cli";
    platforms = lib.platforms.linux;
  };
})
