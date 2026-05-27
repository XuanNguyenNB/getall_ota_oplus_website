-- Expand the live Universal OTA manifest map from the initial subset to the full
-- maintainer-provided REGIONS table and backfill unmodified catalog rows.

alter table public.devices
    drop constraint if exists devices_manifest_code_shape;

alter table public.devices
    add constraint devices_manifest_code_shape check (
        manifest_code is null or manifest_code in (
            '00', 'A4', 'A5', 'A6', 'A7', '1A', '1B', '1E', '2C',
            '33', '37', '38', '39', '3B', '3C', '3E', '44', '51',
            '75', '7B', '82', '83', '8D', '97', '9A', '9E'
        )
    );

alter table public.ota_releases
    drop constraint if exists ota_releases_manifest_code_shape;

alter table public.ota_releases
    add constraint ota_releases_manifest_code_shape check (
        manifest_code in (
            '00', 'A4', 'A5', 'A6', 'A7', '1A', '1B', '1E', '2C',
            '33', '37', '38', '39', '3B', '3C', '3E', '44', '51',
            '75', '7B', '82', '83', '8D', '97', '9A', '9E'
        )
    );

update public.devices
set manifest_code = case
        when upper(product_model) like '%LATAM' then '9A'
        when upper(product_model) like '%EUEX' then '44'
        when upper(product_model) like '%EEA' then '44'
        when upper(product_model) like '%APC' then 'A4'
        when upper(product_model) like '%OCA' then 'A5'
        when upper(product_model) like '%MEA' then 'A6'
        when upper(product_model) like '%ROW' then 'A7'
        when upper(product_model) like '%EU' then '44'
        when upper(product_model) like '%PH' then '3E'
        when upper(product_model) like '%RU' then '37'
        when upper(product_model) like '%SG' then '2C'
        when upper(product_model) like '%TW' then '1A'
        when upper(product_model) like '%JP' then '3B'
        when upper(product_model) like '%SA' then '83'
        when upper(product_model) like '%ID' then '33'
        when upper(product_model) like '%EX' then '00'
        when upper(product_model) like '%MX' then '7B'
        when upper(product_model) like '%AU' then '1E'
        when upper(product_model) like '%HK' then '82'
        when upper(product_model) like '%MY' then '38'
        when upper(product_model) like '%TR' then '51'
        when upper(product_model) like '%EG' then '75'
        when upper(product_model) like '%BR' then '9E'
        when upper(product_model) like '%IN' then '1B'
        when upper(product_model) like '%TH' then '39'
        when upper(product_model) like '%VN' then '3C'
        when upper(product_model) like '%CN' then '97'
    end,
    updated_at = now()
where manual_override = false
  and manifest_code is null
  and (
      upper(product_model) ~ '(LATAM|EUEX|EEA|APC|OCA|MEA|ROW|EU|PH|RU|SG|TW|JP|SA|ID|EX|MX|AU|HK|MY|TR|EG|BR|IN|TH|VN|CN)$'
  );
