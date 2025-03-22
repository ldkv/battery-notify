# Contributing Guidelines

## Table of Contents

- [Development environment](#development-environment)

## Development environment

### Environment variables

Take a look at [.env.default](./.env.default) and generate your own `.env` file with your secrets or customized values.

### Makefile

A [Makefile](./Makefile) is provided to simplify working in development environment.

More details can be found inside the file, or with the command:

```bash
make help
```

### Dependencies management with `uv`

The project uses [uv](https://docs.astral.sh/uv/) for dependencies management.

A make command is provided to execute `uv` with custom `.env` variables:

```bash
make uv -- <uv_command>
# example
make uv -- tree --outdated
```

For more information about dependencies management with `uv`, please refer to the [official documentation](https://docs.astral.sh/uv/concepts/dependencies/).

### Initial setup

- Run the following command **ONCE** to install `uv` and initialize the virtual environment:

```bash
make venv
```

By default, the virtual environment is created in the `.venv` directory. It is possible to change the directory by setting the `UV_PROJECT_ENVIRONMENT` variable in your own [`.env` file](#environment-variables).

```
UV_PROJECT_ENVIRONMENT=/absolute/path/to/your/venv
```

- Install all dependencies:

```bash
make requirements
```

### Local installation from repository

It is possible to install the `battery_notifier` package itself from local source:

```bash
make dev-install
```

### Installing from wheel binary package

First we need to build the package:

```bash
make build
```

This will generate a `dist` folder in the root of the project with the wheel binary package.

To install the package from the wheel binary where XXX is the version number, run:

```bash
uv pip install ./dist/battery_notifier-X.X.X-py3-none-any.whl
```

### Publish the package

To build then publish the package to the internal devpi server, run:

```bash
make publish
```

> [!CAUTION]
> This command is for testing purposes only. For official releases, please refer to the [Releasing](./RELEASING.md) documentation.

### Testing

A convinent command is provided to run the tests locally:

```bash
make test
```

### Code style

The codebase is formatted and linted using `ruff`.

To verify the code style:

```bash
make lint
```

To automatically fix the code style and formatting:

```bash
make lint-fix
```
