-- Two versions of the same supplier must never overlap in time. Returns the offending pairs.
select a.wwi_supplier_id, a.supplier_key as key_a, b.supplier_key as key_b
from {{ ref('dim_supplier') }} as a
join {{ ref('dim_supplier') }} as b
  on a.wwi_supplier_id = b.wwi_supplier_id
 and a.supplier_key < b.supplier_key
 and a.valid_from < b.valid_to
 and b.valid_from < a.valid_to