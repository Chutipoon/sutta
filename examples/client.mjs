const base = process.env.SUTTA_URL ?? 'http://127.0.0.1:8000';
const response = await fetch(`${base}/v1/search`, {
  method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({query: 'sn56.11:1.1', top_k: 5}),
});
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const data = await response.json();
if (data.results[0]?.segment_ids[0] !== 'sn56.11:1.1') throw new Error('Unexpected source segment');
console.log(JSON.stringify(data, null, 2));
