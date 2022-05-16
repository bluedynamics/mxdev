from mxdev.vcs.extension import Source
from mxdev.vcs.tests.utils import Process
from unittest.mock import patch

import os
import pytest
import shutil


class TestGit:
    def createDefaultContent(self, repository):
        # Create default content and branches in a repository.
        # Return a revision number.
        repository.add_file("foo", msg="Initial")
        # create branch for testing
        repository("git checkout -b test", echo=False)
        repository.add_file("foo2")
        # get comitted rev
        lines = repository("git log", echo=False)
        rev = lines[0].split()[1]
        # return to default branch
        repository("git checkout master", echo=False)
        repository.add_file("bar")
        # Return revision of one of the commits, the one that adds the
        # foo2 file.
        return rev

    def testUpdateWithRevisionPin(self, develop, mkgitrepo, src):
        from mxdev.vcs.commands import CmdCheckout
        from mxdev.vcs.commands import CmdStatus
        from mxdev.vcs.commands import CmdUpdate

        repository = mkgitrepo("repository")
        rev = self.createDefaultContent(repository)

        # check rev
        develop.sources = {
            "egg": Source(
                kind="git",
                name="egg",
                rev=rev,
                url="%s" % repository.base,
                path=src["egg"],
            )
        }
        CmdCheckout(develop)(develop.parser.parse_args(["co", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}
        CmdUpdate(develop)(develop.parser.parse_args(["up", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}

        shutil.rmtree(src["egg"])

        # check branch
        develop.sources = {
            "egg": Source(
                kind="git",
                name="egg",
                branch="test",
                url="%s" % repository.base,
                path=src["egg"],
            )
        }
        CmdCheckout(develop)(develop.parser.parse_args(["co", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}
        CmdUpdate(develop)(develop.parser.parse_args(["up", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}
        CmdStatus(develop)(develop.parser.parse_args(["status"]))

        # switch implicitly to master branch
        develop.sources = {
            "egg": Source(
                kind="git", name="egg", url="%s" % repository.base, path=src["egg"]
            )
        }
        CmdUpdate(develop)(develop.parser.parse_args(["up", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}

        # Switch to specific revision, then switch back to master branch.
        develop.sources = {
            "egg": Source(
                kind="git",
                name="egg",
                rev=rev,
                url="%s" % repository.base,
                path=src["egg"],
            )
        }
        CmdUpdate(develop)(develop.parser.parse_args(["up", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}
        develop.sources = {
            "egg": Source(
                kind="git", name="egg", url="%s" % repository.base, path=src["egg"]
            )
        }
        CmdUpdate(develop)(develop.parser.parse_args(["up", "egg"]))
        assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}

        CmdStatus(develop)(develop.parser.parse_args(["status"]))

        # we can't use both rev and branch
        with pytest.raises(SystemExit):
            develop.sources = {
                "egg": Source(
                    kind="git",
                    name="egg",
                    branch="test",
                    rev=rev,
                    url="%s" % repository.base,
                    path=src["egg-failed"],
                )
            }
            CmdCheckout(develop)(develop.parser.parse_args(["co", "egg"]))

    def testUpdateWithoutRevisionPin(self, develop, mkgitrepo, src, capsys):
        from mxdev.vcs.commands import CmdCheckout
        from mxdev.vcs.commands import CmdStatus
        from mxdev.vcs.commands import CmdUpdate

        repository = mkgitrepo("repository")
        repository.add_file("foo")
        repository.add_file("bar")
        repository.add_branch("develop")
        develop.sources = {
            "egg": Source(kind="git", name="egg", url=repository.url, path=src["egg"])
        }
        _log = patch("mxdev.vcs.git.logger")
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(["co", "egg"]))
            assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}
            captured = capsys.readouterr()
            assert captured.out.startswith("Initialized empty Git repository in")
            CmdUpdate(develop)(develop.parser.parse_args(["up", "egg"]))
            assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}
            assert log.method_calls == [
                ("info", ("Cloned 'egg' with git from '%s'." % repository.url,), {}),
                ("info", ("Updated 'egg' with git.",), {}),
                ("info", ("Switching to remote branch 'remotes/origin/master'.",), {}),
            ]
            captured = capsys.readouterr()
            assert captured.out == ""
            CmdStatus(develop)(develop.parser.parse_args(["status", "-v"]))
            captured = capsys.readouterr()
            assert captured.out == "~   A egg\n      ## master...origin/master\n\n"

        finally:
            _log.__exit__(None, None, None)

    def testUpdateVerbose(self, develop, mkgitrepo, src, capsys):
        from mxdev.vcs.commands import CmdCheckout
        from mxdev.vcs.commands import CmdStatus
        from mxdev.vcs.commands import CmdUpdate

        repository = mkgitrepo("repository")
        repository.add_file("foo")
        repository.add_file("bar")
        repository.add_branch("develop")
        develop.sources = {
            "egg": Source(kind="git", name="egg", url=repository.url, path=src["egg"])
        }
        _log = patch("mxdev.vcs.git.logger")
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(["co", "egg", "-v"]))
            assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}
            captured = capsys.readouterr()
            assert captured.out.startswith("Initialized empty Git repository in")
            CmdUpdate(develop)(develop.parser.parse_args(["up", "egg", "-v"]))
            assert set(os.listdir(src["egg"])) == {".git", "bar", "foo"}
            assert log.method_calls == [
                ("info", ("Cloned 'egg' with git from '%s'." % repository.url,), {}),
                ("info", ("Updated 'egg' with git.",), {}),
                ("info", ("Switching to remote branch 'remotes/origin/master'.",), {}),
            ]
            captured = capsys.readouterr()
            older = "* develop\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nBranch master set up to track remote branch master from origin.\n  develop\n* master\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nAlready up-to-date.\n\n"
            newer = "* develop\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nBranch 'master' set up to track remote branch 'master' from 'origin'.\n  develop\n* master\n  remotes/origin/HEAD -> origin/develop\n  remotes/origin/develop\n  remotes/origin/master\nAlready up to date.\n\n"
            # git output varies between versions...
            assert captured.out in [older, newer]
            CmdStatus(develop)(develop.parser.parse_args(["status", "-v"]))
            captured = capsys.readouterr()
            assert captured.out == "~   A egg\n      ## master...origin/master\n\n"

        finally:
            _log.__exit__(None, None, None)

    def testDepthOption(self, mkgitrepo, src, tempdir):
        from mxdev.vcs.develop import develop

        # create repository and make two commits on it
        repository = mkgitrepo("repository")
        self.createDefaultContent(repository)

        tempdir["buildout.cfg"].create_file(
            "[buildout]",
            "mxdev.vcs-threads = 1",
            "[sources]",
            "egg = git %s" % repository.url,
        )
        tempdir[".mxdev.vcs.cfg"].create_file()
        # os.chdir(self.tempdir)
        develop("co", "egg")

        # check that there are two commits in history
        egg_process = Process(cwd=src["egg"])
        lines = egg_process.check_call("git log", echo=False)
        commits = [msg for msg in lines if msg.decode("utf-8").startswith("commit")]
        assert len(commits) == 2

        shutil.rmtree(src["egg"])

        tempdir["buildout.cfg"].create_file(
            "[buildout]",
            "mxdev.vcs-threads = 1",
            "[sources]",
            "egg = git %s depth=1" % repository.url,
        )
        develop("co", "egg")

        # check that there is only one commit in history
        lines = egg_process.check_call("git log", echo=False)
        commits = [msg for msg in lines if msg.decode("utf-8").startswith("commit")]
        assert len(commits) == 1

        shutil.rmtree(src["egg"])

        tempdir["buildout.cfg"].create_file(
            "[buildout]",
            "mxdev.vcs-threads = 1",
            "git-clone-depth = 1",
            "[sources]",
            "egg = git %s" % repository.url,
        )
        develop("co", "egg")

        # check that there is only one commit in history
        lines = egg_process.check_call("git log", echo=False)
        commits = [msg for msg in lines if msg.decode("utf-8").startswith("commit")]
        assert len(commits) == 1

        # You should be able to combine depth and cloning a branch.
        # Otherwise with a depth of 1 you could clone the master
        # branch and then not be able to switch to the wanted branch,
        # because this branch would not be there: the revision that it
        # points to is not in the downloaded history.
        shutil.rmtree(src["egg"])
        tempdir["buildout.cfg"].create_file(
            "[buildout]",
            "mxdev.vcs-threads = 1",
            "git-clone-depth = 1",
            "[sources]",
            "egg = git %s branch=test" % repository.url,
        )
        develop("co", "egg")

        # check that there is only one commit in history
        lines = egg_process.check_call("git log", echo=False)
        commits = [msg for msg in lines if msg.decode("utf-8").startswith("commit")]
        assert len(commits) == 1

        # Check that the expected files from the branch are there
        assert set(os.listdir(src["egg"])) == {".git", "foo", "foo2"}
