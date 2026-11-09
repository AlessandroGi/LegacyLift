{{ config(materialized='table') }}

-- A new version starts when the supplier row or its category row starts a new version.
-- "union" (not "union all") collapses the case where both start at the same instant.
with change_points as (
    select supplier_id, valid_from as changed_at
    from {{ ref('stg_suppliers') }}

    union

    select s.supplier_id, c.valid_from
    from {{ ref('stg_supplier_categories') }} as c
    join {{ ref('stg_suppliers') }} as s
      on s.supplier_category_id = c.supplier_category_id
     and s.valid_from <= c.valid_from and c.valid_from < s.valid_to
),

-- State of the supplier, its category and its contact at each change point.
-- Same rule as FOR SYSTEM_TIME AS OF in the legacy code: valid_from <= t < valid_to.
snapshots as (
    select
        cp.supplier_id,
        cp.changed_at,
        s.supplier_name,
        c.supplier_category_name,
        p.full_name,
        s.supplier_reference,
        s.payment_days,
        s.delivery_postal_code
    from change_points as cp
    join {{ ref('stg_suppliers') }} as s
      on s.supplier_id = cp.supplier_id
     and s.valid_from <= cp.changed_at and cp.changed_at < s.valid_to
    join {{ ref('stg_supplier_categories') }} as c
      on c.supplier_category_id = s.supplier_category_id
     and c.valid_from <= cp.changed_at and cp.changed_at < c.valid_to
    join {{ ref('stg_people') }} as p
      on p.person_id = s.primary_contact_person_id
     and p.valid_from <= cp.changed_at and cp.changed_at < p.valid_to
),

-- A version ends where the next one of the same supplier starts (finding F1 of the
-- legacy code: there the new version took the supplier's own start date and nothing closed the old one).
versions as (
    select
        supplier_id as wwi_supplier_id,
        supplier_name as supplier,
        supplier_category_name as category,
        full_name as primary_contact,
        supplier_reference,
        payment_days,
        delivery_postal_code as postal_code,
        changed_at as valid_from,
        coalesce(
            lead(changed_at) over (partition by supplier_id order by changed_at),
            {{ end_of_time() }}
        ) as valid_to
    from snapshots
)

select
    row_number() over (order by valid_from, wwi_supplier_id) as supplier_key,
    wwi_supplier_id, supplier, category, primary_contact, supplier_reference, payment_days, postal_code,
    valid_from, valid_to
from versions

union all

-- Static "Unknown" member, as in the legacy warehouse (key 0).
select 0, 0, 'Unknown', 'N/A', 'N/A', 'N/A', 0, 'N/A', timestamp '2013-01-01 00:00:00', {{ end_of_time() }}