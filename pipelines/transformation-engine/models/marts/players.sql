with nba as (

    select
        cast(id as int64) as id,
        cast(league as string) as league,
        cast(full_name as string) as full_name,
        cast(first_name as string) as first_name,
        cast(last_name as string) as last_name,
        cast(team_id as int64) as team_id,
        cast(team_abbreviation as string) as team_abbreviation,
        cast(null as string) as position,
        cast(height as string) as height,
        cast(weight as int64) as weight,
        cast(college as string) as college,
        cast(country as string) as country,
        cast(draft_year as int64) as draft_year,
        cast(draft_round as int64) as draft_round,
        cast(draft_number as int64) as draft_number,
        cast(is_active as bool) as is_active
    -- Explicit casts throughout: bio columns (team_id, age, height, weight,
    -- college, country, draft_*) are currently 100% null in raw_nba_api.players
    -- (stats.nba.com's live bio endpoint times out from every environment
    -- tested so far, see nba_api.py's class docstring / CAL-255) -- an
    -- all-null BQ column infers an arbitrary type (seen: INT64 for what
    -- should be STRING), which breaks UNION ALL against wehoop's real
    -- typed data. Cast defensively rather than relying on inference here.
    from {{ ref('stg_nba_api__players') }}

),

wnba as (

    select
        cast(id as int64) as id,
        cast(league as string) as league,
        cast(full_name as string) as full_name,
        cast(first_name as string) as first_name,
        cast(last_name as string) as last_name,
        cast(team_id as int64) as team_id,
        cast(team_abbreviation as string) as team_abbreviation,
        cast(position as string) as position,
        cast(height as string) as height,
        cast(weight as int64) as weight,
        cast(college as string) as college,
        cast(country as string) as country,
        cast(draft_year as int64) as draft_year,
        cast(draft_round as int64) as draft_round,
        cast(draft_number as int64) as draft_number,
        -- wnba_playerindex has no is_active flag (unlike nba_api's static list) --
        -- to_year is the closest available signal: null or the current season
        -- means still active, per CAL-159's own verified spot-check (Diana
        -- Taurasi's to_year=2024 correctly reads as retired). This is a
        -- placeholder heuristic, not a validated mapping - CAL-255 owns
        -- confirming/refining exactly which column(s) determine active status
        -- for both leagues; don't treat this as settled.
        (to_year is null or to_year >= extract(year from current_date())) as is_active
    from {{ ref('stg_wehoop__players') }}

)

select * from nba

union all

select * from wnba
