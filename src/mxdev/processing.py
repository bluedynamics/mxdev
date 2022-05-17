from .logging import logger
from .state import State
from .vcs.common import WorkingCopies
from pathlib import Path
from urllib import parse
from urllib import request

import pkg_resources
import typing


def process_line(
    line: str,
    package_keys: typing.List[str],
    override_keys: typing.List[str],
    ignore_keys: typing.List[str],
    variety: str,
) -> typing.Tuple[typing.List[str], typing.List[str]]:
    if isinstance(line, bytes):
        line = line.decode("utf8")
    logger.debug(f"Process Line [{variety}]: {line.strip()}")
    if line.startswith("-c"):
        return resolve_dependencies(
            line.split(" ")[1].strip(),
            package_keys=package_keys,
            override_keys=override_keys,
            ignore_keys=ignore_keys,
            variety="c",
        )
    elif line.startswith("-r"):
        return resolve_dependencies(
            line.split(" ")[1].strip(),
            package_keys=package_keys,
            override_keys=override_keys,
            ignore_keys=ignore_keys,
            variety="r",
        )
    try:
        parsed = pkg_resources.Requirement.parse(line)
    except Exception:
        pass
    else:
        if parsed.key in package_keys:
            line = f"# {line.strip()} -> mxdev disabled (source)\n"
        if variety == "c" and parsed.key in override_keys:
            line = f"# {line.strip()} -> mxdev disabled (override)\n"
        if variety == "c" and parsed.key in ignore_keys:
            line = f"# {line.strip()} -> mxdev disabled (ignore)\n"
    if variety == "c":
        return [], [line]
    return [line], []


def process_io(
    fio: typing.IO,
    requirements: typing.List[str],
    constraints: typing.List[str],
    package_keys: typing.List[str],
    override_keys: typing.List[str],
    ignore_keys: typing.List[str],
    variety: str,
) -> None:
    for line in fio:
        new_requirements, new_constraints = process_line(
            line, package_keys, override_keys, ignore_keys, variety
        )
        requirements += new_requirements
        constraints += new_constraints


def resolve_dependencies(
    file_or_url: str,
    package_keys: typing.List[str],
    override_keys: typing.List[str],
    ignore_keys: typing.List[str],
    variety: str = "r",
) -> typing.Tuple[typing.List[str], typing.List[str]]:
    requirements: typing.List[str] = []
    constraints: typing.List[str] = []
    if not file_or_url.strip():
        logger.info("mxdev is configured to run without input requirements!")
        return ([], [])
    logger.info(f"Read [{variety}]: {file_or_url}")
    parsed = parse.urlparse(file_or_url)
    variety_verbose = "requirements" if variety == "r" else "constraints"

    if not parsed.scheme:
        requirements_in_file = Path(file_or_url)
        if requirements_in_file.exists():
            with requirements_in_file.open("r") as fio:
                process_io(
                    fio,
                    requirements,
                    constraints,
                    package_keys,
                    override_keys,
                    ignore_keys,
                    variety,
                )
        else:
            logger.info(
                f"Can not read {variety_verbose} file '{file_or_url}', it does not exist. Empty file assumed."
            )
    else:
        with request.urlopen(file_or_url) as fio:
            process_io(
                fio,
                requirements,
                constraints,
                package_keys,
                override_keys,
                ignore_keys,
                variety,
            )

    if requirements and variety == "r":
        requirements = (
            [
                "#" * 79 + "\n",
                f"# begin requirements from: {file_or_url}\n\n",
            ]
            + requirements
            + ["\n", f"# end requirements from: {file_or_url}\n", "#" * 79 + "\n"]
        )
    if constraints and variety == "c":
        constraints = (
            [
                "#" * 79 + "\n",
                f"# begin constraints from: {file_or_url}\n",
                "\n",
            ]
            + constraints
            + ["\n", f"# end constraints from: {file_or_url}\n", "#" * 79 + "\n\n"]
        )
    return (requirements, constraints)


def read(state: State, variety: str = "r") -> None:
    cfg = state.configuration
    state.requirements, state.constraints = resolve_dependencies(
        file_or_url=cfg.infile,
        package_keys=cfg.package_keys,
        override_keys=cfg.override_keys,
        ignore_keys=cfg.ignore_keys,
    )


def autocorrect_pip_url(pip_url: str) -> str:
    """So some autocorrection for pip urls, especially urls copy/pasted
    from github as e.g. git@github.com:bluedynamics/mxdev.git
    which should be git+ssh://git@github.com/bluedynamics/mxdev.git.

    If no correction necessary, return the original value.
    """
    if pip_url.startswith("git@"):
        return f"git+ssh://{pip_url.replace(':', '/')}"
    elif pip_url.startswith("ssh://"):
        return f"git+{pip_url}"
    elif pip_url.startswith("https://"):
        return f"git+{pip_url}"
    return pip_url


def fetch(state: State) -> None:
    packages = state.configuration.packages
    logger.info("#" * 79)
    if not packages:
        logger.info("# No sources configured!")
        return

    logger.info("# Fetch sources from VCS")

    # for name in packages:
    #     logger.info(f"Fetch or update {name}")
    #     package = packages[name]
    #     repo_dir = os.path.abspath(f"{package['target']}/{name}")
    #     pip_url = autocorrect_pip_url(f"{package['url']}@{package['branch']}")
    #     logger.debug(f"pip_url={pip_url} -> repo_dir={repo_dir}")
    #     repo = create_project_from_pip_url(pip_url=pip_url, repo_dir=repo_dir)
    #     repo.update_repo()

    workingcopies = WorkingCopies(packages, threads=1)
    workingcopies.checkout(
        sorted(packages),
        verbose=True,
        update=True,
        submodules="always",
        always_accept_server_certificate=True,
        offline=False,
    )


def write_dev_sources(fio, packages: typing.Dict[str, typing.Dict[str, typing.Any]]):
    fio.write("\n" + "#" * 79 + "\n")
    fio.write("# mxdev development sources\n")
    for name in packages:
        package = packages[name]
        if package["install-mode"] == "skip":
            continue
        extras = f"[{package['extras']}]" if package["extras"] else ""
        subdir = f"/{package['subdirectory']}" if package["subdirectory"] else ""
        install_options = ' --install-option="--pre"'
        editable = (
            f"""-e ./{package['target']}/{name}{subdir}{extras}{install_options}\n"""
        )
        logger.debug(f"-> {editable.strip()}")
        fio.write(editable)
    fio.write("\n")


def write_dev_overrides(
    fio, overrides: typing.Dict[str, str], package_keys: typing.List[str]
):
    fio.write("\n" + "#" * 79 + "\n")
    fio.write("# mxdev constraint overrides\n")
    for pkg, line in overrides.items():
        if pkg in package_keys:
            fio.write(
                f"# {line} IGNORE mxdev constraint override. Source override wins!\n"
            )
        else:
            fio.write(f"{line}\n")
    fio.write("\n")


def write(state: State) -> None:
    requirements = state.requirements
    constraints = state.constraints
    cfg = state.configuration
    logger.info("#" * 79)
    logger.info("# Write outfiles")
    logger.info(f"Write [c]: {cfg.out_constraints}")
    with open(cfg.out_constraints, "w") as fio:
        fio.writelines(constraints)
        if cfg.overrides:
            write_dev_overrides(fio, cfg.overrides, cfg.package_keys)
    logger.info(f"Write [r]: {cfg.out_requirements}")
    with open(cfg.out_requirements, "w") as fio:
        fio.write("#" * 79 + "\n")
        fio.write("# mxdev combined constraints\n")
        fio.write(f"-c {cfg.out_constraints}\n\n")
        write_dev_sources(fio, cfg.packages)
        fio.writelines(requirements)