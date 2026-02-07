{
  description = "Music for the bold and free";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, ... }@inputs:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      forEachSupportedSystem =
        f:
        inputs.nixpkgs.lib.genAttrs supportedSystems (
          system:
          f {
            pkgs = import inputs.nixpkgs { inherit system; };
          }
        );

      version = "3.13";

      concatMajorMinor =
        lib: v:
        lib.pipe v [
          lib.versions.splitVersion
          (lib.sublist 0 2)
          lib.concatStrings
        ];
    in
    {
      packages = forEachSupportedSystem (
        { pkgs }:
        let
          pythonName = "python${concatMajorMinor pkgs.lib version}";
          python = pkgs.${pythonName};

          runScript = pkgs.writeShellApplication {
            name = "run";
            runtimeInputs = [
              python
              python.pkgs.fastapi-cli
              python.pkgs.fastapi
              python.pkgs.yt-dlp
              python.pkgs.flask
              python.pkgs.pydantic
              python.pkgs.python-multipart
              pkgs.ffmpeg
            ];
            text = ''
              ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")

              echo "Moving to project root: $ROOT_DIR"
              cd "$ROOT_DIR"

              exec fastapi dev backend
            '';
          };
        in
        {
          default = runScript;
        }
      );

      devShells = forEachSupportedSystem (
        { pkgs }:
        let
          pythonName = "python${concatMajorMinor pkgs.lib version}";
          python = pkgs.${pythonName};
        in
        {
          default = pkgs.mkShell {
            venvDir = ".venv";

            packages = [
              python
              python.pkgs.venvShellHook
              python.pkgs.fastapi-cli
              python.pkgs.fastapi
              python.pkgs.yt-dlp
              python.pkgs.flask
              python.pkgs.pydantic
              python.pkgs.python-multipart
              pkgs.gh
              pkgs.tmux
              pkgs.ffmpeg
              pkgs.prettier
              self.packages.${pkgs.system}.default
            ];

            postShellHook = ''
              venvVersionWarn() {
                  local venvDir=".venv"
                  if [ -d "$venvDir" ]; then
                      local venvVersion
                      venvVersion="$("$venvDir/bin/python" -c 'import platform; print(platform.python_version())')"
                      if [[ "$venvVersion" != "${python.version}" ]]; then
                          echo "Warning: Python version mismatch!"
                      fi
                  fi
              }
              venvVersionWarn
            '';
          };
        }
      );
    };
}
