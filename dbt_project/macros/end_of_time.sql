{# End of time: the legacy value 9999-12-31 23:59:59.9999999 cut to the 6 decimals PostgreSQL keeps. #}
{% macro end_of_time() %}timestamp '9999-12-31 23:59:59.999999'{% endmacro %}