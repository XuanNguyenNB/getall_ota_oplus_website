-- Smart scan allowlist support: public catalog visibility is separate from
-- worker auto-scan eligibility, and devices are grouped by user-facing model.

alter table public.devices
    add column if not exists catalog_visible boolean not null default true,
    add column if not exists scan_group_key text,
    add column if not exists scan_group_name text;

create or replace function public.infer_device_scan_group_name(
    p_brand text,
    p_name text,
    p_product_model text
)
returns text
language plpgsql
immutable
as $$
declare
    cleaned text := trim(regexp_replace(coalesce(p_name, ''), '\s+', ' ', 'g'));
begin
    loop
        cleaned := trim(regexp_replace(
            cleaned,
            '\s*\((CN|IN|ID|TH|EU|EEA|GLO|GLOBAL|GL|ROW|APC|OCA|MEA|TW|JP|MY|SG|PH|RU|AU|BR|TR|MX|LATAM|SA|HK|EX|EUEX)\)\s*$',
            '',
            'i'
        ));
        exit when cleaned !~* '\s*\((CN|IN|ID|TH|EU|EEA|GLO|GLOBAL|GL|ROW|APC|OCA|MEA|TW|JP|MY|SG|PH|RU|AU|BR|TR|MX|LATAM|SA|HK|EX|EUEX)\)\s*$';
    end loop;

    if cleaned = '' or upper(cleaned) = upper(coalesce(p_product_model, '')) then
        cleaned := regexp_replace(upper(coalesce(p_product_model, '')), '(IN|ID|TH|EEA|EU|MX|MY|JP)$', '');
    end if;

    if p_brand = 'oppo' and cleaned !~* '^oppo\s+' then
        cleaned := 'OPPO ' || cleaned;
    elsif p_brand = 'oneplus' and cleaned !~* '^oneplus\s+' then
        cleaned := 'OnePlus ' || cleaned;
    elsif p_brand = 'realme' and cleaned !~* '^realme\s+' then
        cleaned := 'realme ' || cleaned;
    end if;

    return cleaned;
end;
$$;

create or replace function public.infer_device_scan_group_key(
    p_brand text,
    p_name text,
    p_product_model text
)
returns text
language plpgsql
immutable
as $$
declare
    group_name text := public.infer_device_scan_group_name(p_brand, p_name, p_product_model);
begin
    return trim(both '-' from regexp_replace(lower(group_name), '[^a-z0-9]+', '-', 'g'));
end;
$$;

update public.devices
set scan_group_name = coalesce(
        nullif(scan_group_name, ''),
        public.infer_device_scan_group_name(brand, name, product_model)
    ),
    scan_group_key = coalesce(
        nullif(scan_group_key, ''),
        public.infer_device_scan_group_key(brand, name, product_model)
    ),
    catalog_visible = coalesce(catalog_visible, true);

alter table public.devices
    alter column scan_group_key set not null,
    alter column scan_group_name set not null;

create index if not exists devices_catalog_visible_idx
    on public.devices(catalog_visible);

create index if not exists devices_scan_group_key_idx
    on public.devices(scan_group_key);

create index if not exists devices_scan_group_scan_enabled_idx
    on public.devices(scan_group_key, scan_enabled);

notify pgrst, 'reload schema';
