-- Every supplier must have exactly one current version (valid_to at the end of time).
select wwi_supplier_id, count(*) as open_versions
from {{ ref('dim_supplier') }}
where valid_to = {{ end_of_time() }}
group by wwi_supplier_id
having count(*) <> 1