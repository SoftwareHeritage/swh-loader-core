# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import pkgutil

from swh.loader.tests import assert_task_and_visit_type_match


def test_tasks_loader_visit_type_match_task_name():
    import swh.loader.core
    import swh.loader.package

    modules_ok = []
    modules_ko = []

    modules_seen = set()
    for package in [swh.loader.core, swh.loader.package]:
        package = swh.loader
        prefix = f"{package.__name__}."
        for importer, modname, ispkg in pkgutil.walk_packages(
            package.__path__, prefix=prefix
        ):
            if modname in modules_seen:
                continue
            modules_seen.add(modname)
            # Don't look into test module nor in other non-core or non-package loaders
            if "tasks" in modname and ("package" in modname or "core" in modname):
                try:
                    assert_task_and_visit_type_match(modname)
                    modules_ok.append(modname)
                except AssertionError as e:
                    modules_ko.append((modname, e.args[0]))

    # Raise an error with all problematic modules
    if len(modules_ko) > 0:
        error_message = "\n" + "\n".join(
            f"{module}: {error}" for module, error in modules_ko
        )
        raise AssertionError(error_message)
