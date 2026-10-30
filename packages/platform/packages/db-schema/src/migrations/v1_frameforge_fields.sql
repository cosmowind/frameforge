-- FrameForge plan2 v1 migration — 增 frameforge 上传参数字段
-- 时间：2026-07-14
-- 触发：调研 frameforge vendorTaskBoxes / vendorVideos / vendors 表
-- 红线：只 ADD COLUMN，不改已有列类型，不 DROP
-- 写完后请人工 SQL 验证

-- videos 新增
ALTER TABLE public.videos ADD COLUMN IF NOT EXISTS country_code text;
ALTER TABLE public.videos ADD COLUMN IF NOT EXISTS region text;
ALTER TABLE public.videos ADD COLUMN IF NOT EXISTS folder_name text;
ALTER TABLE public.videos ADD COLUMN IF NOT EXISTS storage_provider text DEFAULT 'cos';
ALTER TABLE public.videos ADD COLUMN IF NOT EXISTS file_size_bytes bigint;
ALTER TABLE public.videos ADD COLUMN IF NOT EXISTS fps double precision;
ALTER TABLE public.videos ADD COLUMN IF NOT EXISTS frame_count integer;

-- environments 新增
ALTER TABLE public.environments ADD COLUMN IF NOT EXISTS country_code text;
ALTER TABLE public.environments ADD COLUMN IF NOT EXISTS region text;
ALTER TABLE public.environments ADD COLUMN IF NOT EXISTS scene_custom_label text;

-- 索引：录制员/任务常用按 country/region 筛
CREATE INDEX IF NOT EXISTS videos_country_idx ON public.videos (country_code);
CREATE INDEX IF NOT EXISTS videos_region_idx ON public.videos (region);
CREATE INDEX IF NOT EXISTS videos_storage_idx ON public.videos (storage_provider);
CREATE INDEX IF NOT EXISTS environments_country_idx ON public.environments (country_code);
