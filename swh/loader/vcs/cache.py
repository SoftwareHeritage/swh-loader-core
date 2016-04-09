# Copyright (C) 2015-2016  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from collections import deque


class SimpleCache():
    def __init__(self, max_size=10000, eviction_percent=0.2):
        """Initialize cache of max_size elements.

           Args:

           - max_size: the max number of elements to cache.
           - eviction_percent: Percent of elements to evict from cache
           when max_size is reached. The eviction removes the first
           elements from the cache.

        """
        self.max_size = max_size
        assert eviction_percent >= 0 and eviction_percent <= 1
        self.nb_elements_to_purge = int(max_size * eviction_percent)
        self.s = set()
        self.stack = deque([], maxlen=max_size)
        self.count = 0

    def __str__(self):
        return ('set: %s, stack: %s, count: %s, max-size: %s, nb-purge: %s' % (
            self.s,
            self.stack,
            self.count,
            self.max_size,
            self.nb_elements_to_purge))

    def _evict(self):
        """Remove self.nb_elements_to_purge from cache.

        """
        elems_to_remove = set()
        for x in range(0, self.nb_elements_to_purge):
            e = self.stack.popleft()
            elems_to_remove.add(e)
        self.s = self.s - elems_to_remove
        self.count = self.count - self.nb_elements_to_purge

    def add(self, e):
        if e not in self.s:
            self.s.add(e)
            self.stack.append(e)
            self.count += 1

            if self.count >= self.max_size:
                self._evict()

    def set(self):
        return self.s
