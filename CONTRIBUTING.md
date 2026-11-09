# Contributing Guidelines

## Table of Contents

- [Development environment](#development-environment)

## Development environment

See [Development](./README.md#development) in the README to install the toolchain and the system libraries.

### Taskfile

A [Taskfile](./Taskfile.yml) is provided to simplify working in development environment.

More details can be found inside the file, or with the command:

```bash
task --help
```

### Testing

A convenient command is provided to run the tests locally:

```bash
task test
```

### Code style

The codebase is formatted with `rustfmt` and linted with `clippy`.

To verify the code style:

```bash
task code-quality
```

To automatically fix the code style and formatting:

```bash
task format
task lint-fix
```
