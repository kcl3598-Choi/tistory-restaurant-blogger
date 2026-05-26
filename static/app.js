// 전역 상태
let selectedRestaurant = null;
let selectedFiles = [];
let generatedPost = null;
let currentJobId = null;
let pollInterval = null;

// ── 식당 검색 ──────────────────────────────────────────────

async function searchRestaurant() {
  const query = document.getElementById('search-input').value.trim();
  if (!query) return alert('식당명을 입력하세요.');

  const btn = document.getElementById('search-btn');
  btn.textContent = '검색 중...';
  btn.disabled = true;

  try {
    const fd = new FormData();
    fd.append('query', query);
    const res = await fetch('/search-restaurant', { method: 'POST', body: fd });
    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || '검색 실패');
      return;
    }

    renderSearchResults(data.results || []);
  } catch (e) {
    alert('검색 중 오류: ' + e.message);
  } finally {
    btn.textContent = '검색';
    btn.disabled = false;
  }
}

function renderSearchResults(results) {
  const container = document.getElementById('search-results');
  if (!results.length) {
    container.innerHTML = '<p class="text-gray-400 text-sm text-center py-2">검색 결과가 없습니다.</p>';
    container.classList.remove('hidden');
    return;
  }

  container.innerHTML = results.map((r, i) => `
    <div class="border border-gray-200 rounded-xl p-3 cursor-pointer hover:border-indigo-400 hover:bg-indigo-50 transition"
         onclick="selectRestaurant(${i})">
      <div class="flex justify-between items-start">
        <div>
          <p class="font-medium text-gray-800 text-sm">${r.name}</p>
          <p class="text-xs text-gray-500 mt-0.5">${r.category || ''}</p>
          <p class="text-xs text-gray-500">${r.address || ''}</p>
        </div>
        ${r.phone ? `<span class="text-xs text-gray-400 ml-2 shrink-0">${r.phone}</span>` : ''}
      </div>
    </div>
  `).join('');

  container.classList.remove('hidden');
  // 결과를 전역에 저장
  container._results = results;
}

function selectRestaurant(idx) {
  const container = document.getElementById('search-results');
  const results = container._results;
  if (!results) return;

  selectedRestaurant = results[idx];

  document.getElementById('sel-name').textContent = selectedRestaurant.name;
  document.getElementById('sel-address').textContent = selectedRestaurant.address || '';
  document.getElementById('sel-phone').textContent = selectedRestaurant.phone || '';
  document.getElementById('selected-restaurant').classList.remove('hidden');
  container.classList.add('hidden');
}

function clearRestaurant() {
  selectedRestaurant = null;
  document.getElementById('selected-restaurant').classList.add('hidden');
  document.getElementById('search-input').value = '';
}

// 엔터로 검색
document.getElementById('search-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') searchRestaurant();
});

// ── 이미지 업로드 ──────────────────────────────────────────

function onDragOver(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.add('drag-over');
}
function onDragLeave(e) {
  document.getElementById('drop-zone').classList.remove('drag-over');
}
function onDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag-over');
  addFiles([...e.dataTransfer.files]);
}
function onFileSelect(e) {
  addFiles([...e.target.files]);
}

function addFiles(files) {
  const imageFiles = files.filter(f => f.type.startsWith('image/'));
  const remaining = 10 - selectedFiles.length;
  const toAdd = imageFiles.slice(0, remaining);
  selectedFiles.push(...toAdd);
  renderImagePreviews();
}

function removeFile(idx) {
  selectedFiles.splice(idx, 1);
  renderImagePreviews();
}

function renderImagePreviews() {
  const container = document.getElementById('image-preview');
  if (!selectedFiles.length) {
    container.classList.add('hidden');
    return;
  }
  container.classList.remove('hidden');
  container.innerHTML = selectedFiles.map((f, i) => `
    <div class="relative group">
      <img src="${URL.createObjectURL(f)}" class="w-full aspect-square object-cover rounded-lg">
      <button onclick="removeFile(${i})"
              class="absolute top-1 right-1 bg-black/60 text-white rounded-full w-5 h-5 text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition">✕</button>
    </div>
  `).join('');
}

// ── 블로그 글 생성 ─────────────────────────────────────────

async function generatePost() {
  if (!selectedRestaurant && !document.getElementById('search-input').value.trim()) {
    alert('식당을 검색하고 선택해주세요.');
    return;
  }

  setLoading(true, '사진을 분석하고 블로그 글을 작성하는 중... (30~60초 소요)');

  try {
    const fd = new FormData();
    const r = selectedRestaurant || {};
    fd.append('restaurant_name', r.name || document.getElementById('search-input').value.trim());
    fd.append('restaurant_address', r.address || '');
    fd.append('restaurant_phone', r.phone || '');
    fd.append('restaurant_category', r.category || '');
    fd.append('restaurant_url', r.url || '');
    fd.append('visit_date', document.getElementById('visit-date').value);
    fd.append('extra_notes', document.getElementById('extra-notes').value);

    for (const f of selectedFiles) fd.append('images', f);

    const res = await fetch('/generate', { method: 'POST', body: fd });
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || '글 생성 실패');

    generatedPost = data;
    renderStep2(data);
    goToStep(2);
  } catch (e) {
    alert('오류: ' + e.message);
  } finally {
    setLoading(false);
  }
}

function setLoading(show, msg = '') {
  document.getElementById('loading').classList.toggle('hidden', !show);
  document.getElementById('generate-btn').disabled = show;
  if (msg) document.getElementById('loading-msg').textContent = msg;
}

// ── Step 2: 글 미리보기 렌더링 ────────────────────────────

function renderStep2(data) {
  document.getElementById('post-title').value = data.title || '';
  document.getElementById('post-meta').value = data.meta_description || '';
  updateMetaLen();
  document.getElementById('post-content').value = data.content || '';
  syncPreview();

  // 태그
  const tags = data.tags || [];
  document.getElementById('post-tags-raw').value = tags.join(',');
  document.getElementById('tag-list').innerHTML = tags.map((t, i) => `
    <span class="bg-indigo-100 text-indigo-700 text-xs px-2.5 py-1 rounded-full flex items-center gap-1">
      ${t}
      <button onclick="removeTag(${i})" class="hover:text-red-500">✕</button>
    </span>
  `).join('');

  // SEO 키워드
  const keywords = data.seo_keywords || [];
  document.getElementById('seo-keywords').innerHTML = keywords.map(k =>
    `<span class="bg-green-100 text-green-700 text-xs px-2.5 py-1 rounded-full">${k}</span>`
  ).join('');
}

function removeTag(idx) {
  const raw = document.getElementById('post-tags-raw').value;
  const tags = raw.split(',').filter(Boolean);
  tags.splice(idx, 1);
  document.getElementById('post-tags-raw').value = tags.join(',');
  renderStep2({ ...generatedPost, tags, content: document.getElementById('post-content').value });
}

function updateMetaLen() {
  const val = document.getElementById('post-meta').value;
  document.getElementById('meta-len').textContent = `(${val.length}/160자)`;
}
document.getElementById('post-meta').addEventListener('input', updateMetaLen);

function switchTab(tab) {
  const isEdit = tab === 'edit';
  document.getElementById('post-content').classList.toggle('hidden', !isEdit);
  document.getElementById('preview-pane').classList.toggle('hidden', isEdit);
  document.getElementById('tab-edit').className = isEdit
    ? 'text-sm font-medium px-3 py-1 rounded bg-indigo-100 text-indigo-700'
    : 'text-sm font-medium px-3 py-1 rounded text-gray-500 hover:bg-gray-100';
  document.getElementById('tab-preview').className = !isEdit
    ? 'text-sm font-medium px-3 py-1 rounded bg-indigo-100 text-indigo-700'
    : 'text-sm font-medium px-3 py-1 rounded text-gray-500 hover:bg-gray-100';
  if (!isEdit) syncPreview();
}

function syncPreview() {
  const md = document.getElementById('post-content').value;
  document.getElementById('preview-pane').innerHTML = marked.parse(md);
}

// ── Step 3: 발행 ──────────────────────────────────────────

function goToStep(n) {
  document.getElementById('step1').classList.toggle('hidden', n !== 1);
  document.getElementById('step2').classList.toggle('hidden', n !== 2);
  document.getElementById('step3').classList.toggle('hidden', n !== 3);

  const steps = ['step1-ind', 'step2-ind', 'step3-ind'];
  steps.forEach((id, i) => {
    const el = document.getElementById(id);
    el.className = 'step-indicator w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ';
    if (i + 1 < n) el.className += 'done';
    else if (i + 1 === n) el.className += 'active';
    else el.className += 'bg-gray-200 text-gray-500';
  });

  if (n === 3) {
    const title = document.getElementById('post-title').value;
    const tags = document.getElementById('post-tags-raw').value.split(',').filter(Boolean);
    const chars = document.getElementById('post-content').value.length;
    document.getElementById('sum-title').textContent = title;
    document.getElementById('sum-tags').textContent = `${tags.length}개`;
    document.getElementById('sum-chars').textContent = `${chars.toLocaleString()}자`;
  }
}

function toggleSchedule() {
  const type = document.querySelector('input[name="publish-type"]:checked').value;
  document.getElementById('schedule-picker').classList.toggle('hidden', type !== 'schedule');
}

async function submitPost() {
  const title = document.getElementById('post-title').value.trim();
  const content = document.getElementById('post-content').value.trim();
  const tags = document.getElementById('post-tags-raw').value;
  const publishType = document.querySelector('input[name="publish-type"]:checked').value;
  const scheduledAt = publishType === 'schedule' ? document.getElementById('scheduled-at').value : '';

  if (!title) return alert('제목을 입력하세요.');
  if (!content) return alert('내용이 없습니다.');
  if (publishType === 'schedule' && !scheduledAt) return alert('예약 발행 시간을 선택하세요.');

  document.getElementById('post-btn').disabled = true;
  document.getElementById('post-loading').classList.remove('hidden');
  document.getElementById('post-result').classList.add('hidden');
  document.getElementById('post-error').classList.add('hidden');

  try {
    const fd = new FormData();
    fd.append('title', title);
    fd.append('content', content);
    fd.append('tags', tags);
    fd.append('image_paths', (generatedPost?.image_paths || []).join('|'));
    fd.append('scheduled_at', scheduledAt);

    const res = await fetch('/post', { method: 'POST', body: fd });
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || '발행 요청 실패');

    currentJobId = data.job_id;

    if (data.status === 'scheduled') {
      document.getElementById('post-loading').classList.add('hidden');
      showSuccess(null, `예약 발행 등록 완료 (${scheduledAt})`);
    } else {
      // 즉시 발행: 상태 폴링
      pollInterval = setInterval(pollJobStatus, 3000);
    }
  } catch (e) {
    document.getElementById('post-loading').classList.add('hidden');
    document.getElementById('post-btn').disabled = false;
    showError(e.message);
  }
}

async function pollJobStatus() {
  if (!currentJobId) return;
  try {
    const res = await fetch(`/status/${currentJobId}`);
    const data = await res.json();

    if (data.status === 'done') {
      clearInterval(pollInterval);
      document.getElementById('post-loading').classList.add('hidden');
      showSuccess(data.url);
    } else if (data.status === 'error') {
      clearInterval(pollInterval);
      document.getElementById('post-loading').classList.add('hidden');
      document.getElementById('post-btn').disabled = false;
      showError(data.error || '알 수 없는 오류');
    }
  } catch (e) {
    // 폴링 오류는 무시하고 계속 시도
  }
}

function showSuccess(url, msg) {
  const el = document.getElementById('post-result');
  el.classList.remove('hidden');
  if (url) {
    const link = document.getElementById('post-url');
    link.href = url;
    link.textContent = url;
  } else if (msg) {
    document.getElementById('post-url').textContent = msg;
  }
}

function showError(msg) {
  document.getElementById('post-error').classList.remove('hidden');
  document.getElementById('post-error-msg').textContent = msg;
}

function resetAll() {
  selectedRestaurant = null;
  selectedFiles = [];
  generatedPost = null;
  currentJobId = null;
  if (pollInterval) clearInterval(pollInterval);

  document.getElementById('search-input').value = '';
  document.getElementById('search-results').classList.add('hidden');
  document.getElementById('selected-restaurant').classList.add('hidden');
  document.getElementById('image-preview').classList.add('hidden');
  document.getElementById('file-input').value = '';
  document.getElementById('visit-date').value = '';
  document.getElementById('extra-notes').value = '';
  document.getElementById('post-result').classList.add('hidden');
  document.getElementById('post-error').classList.add('hidden');
  document.getElementById('post-btn').disabled = false;

  goToStep(1);
}
