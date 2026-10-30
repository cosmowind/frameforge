const { Client } = require('pg');
(async () => {
  const c = new Client({ connectionString: 'postgresql://ffuser:changeme@db.example.com:5432/video_manager' });
  await c.connect();
  console.log('===== 8 旧表 schema =====');
  const cols = await c.query(`
    SELECT t.tablename, c.column_name, c.data_type, c.is_nullable
    FROM pg_tables t
    JOIN information_schema.columns c
      ON c.table_schema = t.schemaname AND c.table_name = t.tablename
    WHERE t.schemaname = 'public'
    ORDER BY t.tablename, c.ordinal_position
  `);
  let last = null;
  cols.rows.forEach(r => {
    if (last !== r.tablename) { last = r.tablename; console.log(`\n[${r.tablename}]`); }
    console.log(`  ${r.column_name.padEnd(30)} ${r.data_type.padEnd(20)} ${r.is_nullable === 'NO' ? 'NOT NULL' : 'NULL'}`);
  });
  console.log('\n===== 行数 =====');
  for (const t of ['app_config','recorders','environments','sd_cards','tasks','video_batch_config','videos','videos_backup_focused']) {
    const r = await c.query(`SELECT count(*)::int AS n FROM public.${t}`);
    console.log(`  ${t.padEnd(25)} ${r.rows[0].n}`);
  }
  console.log('\n===== videos 前 3 行 =====');
  const sample = await c.query(`SELECT * FROM public.videos LIMIT 3`);
  sample.rows.forEach((r, i) => {
    console.log(`\n[${i}]`);
    Object.entries(r).forEach(([k, v]) => console.log(`  ${k}: ${JSON.stringify(v)?.slice(0,80) ?? v}`));
  });
  await c.end();
})().catch(e => { console.error('FAIL', e.code||'', e.message); process.exit(2); });
