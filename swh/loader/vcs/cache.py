# Copyright (C) 2015-2016  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from cachetools.lfu import LFUCache


class SimpleCache(LFUCache):
    def __init__(self, maxsize=10000, eviction_percent=0.2):
        """Initialize a cache of maxsize elements.

           When the maxsize is hit, an eviction routine is triggered
           to remove the least frequently used hit data.

           Args:
           - maxsize: the max number of elements to cache.
           - eviction_percent: Percent of elements to evict from cache
           when maxsize is reached. The eviction removes the lfu
           elements from the cache.

        """
        super().__init__(maxsize=maxsize)
        assert eviction_percent >= 0 and eviction_percent <= 1
        self.nb_elements_to_purge = int(maxsize * eviction_percent)

    def _evict(self):
        """Remove self.nb_elements_to_purge from cache.

        """
        for _ in range(0, self.nb_elements_to_purge):
            self.popitem()

    def add(self, e):
        if self.currsize+1 >= self.maxsize:
            self._evict()
        super().__setitem__(key=e, value=e)

    def __contains__(self, e):
        try:
            self.__getitem__(e)
        except:
            return False
        else:
            return True
