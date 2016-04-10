# Copyright (C) 2015-2016  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import unittest

from nose.tools import istest

from swh.loader.vcs.cache import SimpleCache


class TestSimpleCache(unittest.TestCase):

    @istest
    def simple_cache_behavior_fails_to_init(self):
        try:
            SimpleCache(maxsize=6, eviction_percent=10)
        except AssertionError:
            self.assertTrue(True)

    @istest
    def simple_cache_behavior(self):
        # given
        cache = SimpleCache(maxsize=6, eviction_percent=0.5)

        cache.add(3)
        cache.add(2)
        cache.add(1)

        # when
        self.assertTrue(1 in cache)
        self.assertTrue(2 in cache)
        self.assertTrue(3 in cache)

        self.assertFalse(4 in cache)

        cache.add(4)
        cache.add(5)

        self.assertTrue(1 in cache)
        self.assertTrue(2 in cache)
        self.assertTrue(3 in cache)
        self.assertTrue(4 in cache)
        self.assertTrue(5 in cache)

        self.assertFalse(6 in cache)

        self.assertEquals(cache.__getitem__(4), 4)  # increment their use
        self.assertEquals(cache.__getitem__(5), 5)  # increment their use

        cache.add(4)
        cache.add(4)   # increment their use
        cache.add(5)
        cache.add(5)   # increment their use
        cache.add(6)   # we hit maxsize

        self.assertTrue(4 in cache)
        self.assertTrue(5 in cache)
        self.assertTrue(6 in cache)

        # stat on counts (each in action and get action increments use with 1):
        # 1: 3
        # 2: 3
        # 3: 3
        # 4: 5
        # 5: 5
        # 6: 1  # 6 is inserted after eviction. Else it could never be inserted

        # we hit the max size of 6 so 50% of data (3) will be removed.
        # As 1, 2, 3 are the least frequently used so they are the ones evicted
        self.assertFalse(1 in cache)
        self.assertFalse(2 in cache)
        self.assertFalse(3 in cache)

        cache.add(7)
        cache.add(8)
        self.assertTrue(7 in cache)
        self.assertTrue(8 in cache)
