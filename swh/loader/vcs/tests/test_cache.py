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
            SimpleCache(max_size=6, eviction_percent=10)
        except AssertionError:
            self.assertTrue(True)

    @istest
    def simple_cache_behavior(self):
        # given
        cache = SimpleCache(max_size=6, eviction_percent=0.5)

        cache.add(3)
        cache.add(2)
        cache.add(1)
        cache.add(1)  # duplicate elements are dismissed

        # when
        self.assertEquals(cache.set(), {1, 2, 3})
        self.assertEquals(cache.count, 3)

        cache.add(4)
        cache.add(5)

        self.assertEquals(cache.set(), {1, 2, 3, 4, 5})
        self.assertEquals(cache.count, 5)

        cache.add(6)  # we hit max-size, 50% of elements (here 3) are evicted

        self.assertEquals(cache.set(), {4, 5, 6})
        self.assertEquals(cache.count, 3)

        cache.add(7)
        cache.add(8)
        self.assertEquals(cache.set(), {4, 5, 6, 7, 8})
        self.assertEquals(cache.count, 5)
