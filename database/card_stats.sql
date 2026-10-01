SELECT
    *
FROM
    oneapp.familybot_failed_cards
ORDER BY
    card_id desc;

SELECT
    CASE
        WHEN reason_for_fail LIKE '%failed on fifth attempt%'
        OR reason_for_fail LIKE '%failed after 4 times%' THEN '5th'
        WHEN reason_for_fail LIKE '%failed on third attempt %' THEN '3th'
        WHEN reason_for_fail LIKE '%failed on second attempt%' THEN '2th'
        WHEN reason_for_fail LIKE '%failed on first attempt%' THEN '1th'
        ELSE 'Normal'
    END AS attempt,
    COUNT(*)
FROM
    oneapp.familybot_failed_cards
WHERE
    country = 'poland2'
GROUP BY
    1;