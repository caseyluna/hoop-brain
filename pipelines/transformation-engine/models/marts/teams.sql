select * from {{ ref('stg_nba_api__teams') }}

union all

select * from {{ ref('stg_wehoop__teams') }}
