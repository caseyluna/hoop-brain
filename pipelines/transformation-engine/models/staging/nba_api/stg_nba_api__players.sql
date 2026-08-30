with source as (

    select * from {{ source('nba_api', 'players') }}

),

deduped as (

    select
        id,
        full_name,
        first_name,
        last_name,
        is_active,
        league,
        team_id,
        team_abbreviation,
        age,
        height,
        height_inches,
        weight,
        college,
        country,
        draft_year,
        draft_round,
        draft_number
    from source
    qualify row_number() over (partition by id order by id) = 1

)

select * from deduped
