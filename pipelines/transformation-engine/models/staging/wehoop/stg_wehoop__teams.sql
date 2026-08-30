with source as (

    select * from {{ source('wehoop', 'teams') }}

),

deduped as (

    select
        id,
        full_name,
        abbreviation,
        nickname,
        city,
        -- state/year_founded are always null for this source (ESPN doesn't
        -- publish them for WNBA teams) — cast explicitly rather than let
        -- BigQuery infer a type from an all-null Parquet column, which can
        -- land on something other than stg_nba_api__teams's STRING/INT64
        -- and break the marts.teams UNION ALL.
        cast(state as string) as state,
        cast(year_founded as int64) as year_founded,
        league
    from source
    qualify row_number() over (partition by id order by id) = 1

)

select * from deduped
