with source as (

    select * from {{ source('wehoop', 'players') }}

),

deduped as (

    select
        id,
        full_name,
        first_name,
        last_name,
        league,
        team_id,
        team_abbreviation,
        position,
        height,
        weight,
        college,
        country,
        draft_year,
        draft_round,
        draft_number,
        roster_status,
        from_year,
        to_year
    from source
    qualify row_number() over (partition by id order by id) = 1

)

select * from deduped
