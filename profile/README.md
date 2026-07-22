# Private career profile

The YAML files directly inside this directory contain private user data and are
ignored by Git. Sanitized, structurally valid starter files live in
`profile/templates/` and are safe to commit.

Initialize a fresh clone with:

```bash
python3 scripts/initialize_profile.py
```

The initializer creates only missing files and never overwrites an existing
career profile. Back up the private YAML files separately; they are not stored
in the repository or its remote.
