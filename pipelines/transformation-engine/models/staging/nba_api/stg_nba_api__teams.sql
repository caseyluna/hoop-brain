with source as (

    select * from {{ source('nba_api', 'teams') }}

),

deduped as (

    select
        id,
        full_name,
        abbreviation,
        nickname,
        city,
        state,
        year_founded,
        league
    from source
    qualify row_number() over (partition by id order by id) = 1

)

select * from deduped
