# Secret Handling

- Prefer chezmoi-native secret handling over hardcoded values.
- For 1Password-backed values, prefer chezmoi's native 1Password integration when the config supports it.
- Do not commit raw secrets into the source tree.
- If a file is sensitive, use the correct chezmoi private-file pattern instead of relying on convention alone.
