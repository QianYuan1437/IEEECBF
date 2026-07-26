const { createApp, ref, computed, watch, onMounted } = Vue;

createApp({
  setup() {
    const tabs = [
      { id: 'all', label: 'All Papers' },
      { id: 'journal', label: 'Journals' },
      { id: 'conference', label: 'Conferences' },
      { id: 'high_cited', label: 'High Cited' },
    ];

    const activeTab = ref('all');

    const searchKeyword = ref('');
    const customKeywords = ref('');
    const customKeywordMode = ref(false);
    const sortBy = ref('date');
    const sortOpen = ref(false);
    const venueFilter = ref('');

    const refinedKeywords = ref([]);
    const activeRefinedCodes = ref(['PTC']);
    const venues = ref([]);

    const currentPapers = ref([]);
    const totalPapers = ref(0);

    const cacheLoaded = ref(false);
    const totalCached = ref(0);
    const searching = ref(false);
    const refreshing = ref(false);
    const hasSearched = ref(false);

    const sortLabel = computed(() =>
      sortBy.value === 'citations' ? 'Sort by Citations' : 'Sort by Time'
    );

    function isRefinedActive(code) {
      return activeRefinedCodes.value.includes(code);
    }

    function toggleRefined(code) {
      const idx = activeRefinedCodes.value.indexOf(code);
      if (idx >= 0) {
        activeRefinedCodes.value.splice(idx, 1);
      } else {
        activeRefinedCodes.value.push(code);
      }
      doLocalSearch();
    }

    function chooseSort(type) {
      sortBy.value = type;
      sortOpen.value = false;
      doLocalSearch();
    }

    async function loadKeywordsAndVenues() {
      try {
        const kwResp = await fetch('/api/keywords');
        const kwData = await kwResp.json();
        refinedKeywords.value = kwData.keywords || [];
      } catch (e) {
        console.error('Failed to load keywords:', e);
      }

      try {
        const vResp = await fetch('/api/venues');
        const vData = await vResp.json();
        venues.value = vData.venues || [];
      } catch (e) {
        console.error('Failed to load venues:', e);
      }
    }

    async function checkHealth() {
      try {
        const resp = await fetch('/api/health');
        const data = await resp.json();
        cacheLoaded.value = data.cache_loaded;
        totalCached.value = (data.cache_papers?.latest || 0)
          + (data.cache_papers?.high_cited || 0)
          + (data.cache_papers?.arxiv || 0);
      } catch (e) {
        cacheLoaded.value = false;
      }
    }

    async function doLocalSearch() {
      hasSearched.value = true;
      let source = 'all';
      if (activeTab.value === 'journal') source = 'all';
      else if (activeTab.value === 'high_cited') source = 'high_cited';

      const params = new URLSearchParams();
      if (searchKeyword.value.trim()) params.set('keyword', searchKeyword.value.trim());
      activeRefinedCodes.value.forEach(c => params.append('refined', c));
      if (venueFilter.value) params.set('venue', venueFilter.value);
      params.set('source', source);
      params.set('sort', sortBy.value);
      params.set('limit', '200');

      try {
        const resp = await fetch(`/api/search?${params.toString()}`);
        const data = await resp.json();
        currentPapers.value = data.papers || [];
        totalPapers.value = data.total || 0;
      } catch (e) {
        console.error('Local search failed:', e);
      }
    }

    async function doRealtimeSearch() {
      searching.value = true;
      hasSearched.value = true;

      const params = new URLSearchParams();
      const kw = searchKeyword.value.trim() || customKeywords.value.trim();
      if (kw) params.set('keyword', kw);
      activeRefinedCodes.value.forEach(c => params.append('refined', c));
      params.set('max_results', '50');

      try {
        const resp = await fetch(`/api/search/realtime?${params.toString()}`);
        const data = await resp.json();
        currentPapers.value = data.papers || [];
        totalPapers.value = data.total || 0;
      } catch (e) {
        console.error('Realtime search failed:', e);
      } finally {
        searching.value = false;
      }
    }

    async function doRefreshCache() {
      refreshing.value = true;
      try {
        await fetch('/api/refresh', { method: 'POST' });
        await checkHealth();
        await loadKeywordsAndVenues();
        await doLocalSearch();
      } catch (e) {
        console.error('Cache refresh failed:', e);
      } finally {
        refreshing.value = false;
      }
    }

    let debounceTimer = null;
    function onSearchInput() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        doLocalSearch();
      }, 400);
    }

    watch(activeTab, () => {
      doLocalSearch();
    });

    watch(venueFilter, () => {
      doLocalSearch();
    });

    document.addEventListener('click', (e) => {
      const wrap = document.querySelector('.sort-wrap');
      if (wrap && !wrap.contains(e.target)) {
        sortOpen.value = false;
      }
    });

    onMounted(async () => {
      await checkHealth();
      await loadKeywordsAndVenues();
      doLocalSearch();
    });

    return {
      tabs, activeTab,
      searchKeyword, customKeywords, customKeywordMode,
      sortBy, sortOpen, sortLabel,
      venueFilter, venues,
      refinedKeywords, activeRefinedCodes,
      currentPapers, totalPapers,
      cacheLoaded, totalCached,
      searching, refreshing, hasSearched,
      isRefinedActive, toggleRefined,
      chooseSort,
      doLocalSearch, doRealtimeSearch, doRefreshCache,
      onSearchInput,
    };
  },
}).mount('#app');
