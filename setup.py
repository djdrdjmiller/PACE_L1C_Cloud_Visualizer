"""Wheel builds require the pinned frontend build; wheel users do not need Node."""
from pathlib import Path
import shutil
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithFrontend(build_py):
    def run(self):
        super().run()
        source = Path(__file__).parent / 'frontend' / 'dist'
        if not (source / 'index.html').is_file():
            raise RuntimeError('Build frontend first: cd frontend && pnpm install --frozen-lockfile && pnpm run build. End users should install the GitHub release wheel.')
        target = Path(self.build_lib) / 'pace_l1c' / 'web'
        if target.exists():
            shutil.rmtree(target)  # This build's generated web assets only, never science/cache inputs.
        shutil.copytree(source, target)


setup(cmdclass={'build_py': BuildWithFrontend})
