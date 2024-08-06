# Contributing
## Development Environment
This project uses [Poetry](https://python-poetry.org/) to manage dependencies. With your fork cloned to your local machine, you can install the project and its dependencies to create a development environment using:

```bash
$ poetry install
```

A [`pre-commit`](https://pre-commit.com) configuration is also provided to create a pre-commit hook so linting errors aren't committed:

```bash
$ pre-commit install
```

## Testing & Coverage
A [pytest](https://docs.pytest.org/en/latest/) suite is provided, with coverage reporting from [`pytest-cov`](https://github.com/pytest-dev/pytest-cov). A [`tox`](https://github.com/tox-dev/tox/) configuration is provided to test across all supported versions of Python. Testing will be skipped for Python versions that cannot be found.

```bash
$ tox
```

Details on missing coverage, including in the test suite, is provided in the report to allow the user to generate additional tests for full coverage. Full code coverage is expected for the majority of code contributed to this project. Some exceptions are expected, primarily around code whose functionality relies on either user input or the presence of external drives; these interactions are currently not mocked, though this may change in the future.

## Documentation
### `pdoc`
Autogenerated documentation is provided by [`pdoc`](https://pdoc3.github.io/pdoc/) & deployed on pushes to the `main` branch of the project. The included `tox` configuration will also regenerate the static HTML pages, and you can also invoke manually using:

```bash
$ tox -e pdoc
```

### `cog`
The project README contains some dynamic content generated by [`cog`](https://cog.readthedocs.io/en/latest/). The included `tox` configuration will also these sections, and you can also invoke manually using:

```bash
$ tox -e cog
```