# blueco-reporting

BlueCo's Amazon client reporting: the weekly inventory report and the mid-month /
end-of-month client reports, run by Claude from DataDoe data and posted to internal Slack.

Start with [SOP.md](SOP.md).

```
clients/          one YAML per client: DataDoe account, currency, Slack channel, lead time, notes
config/           published dashboards the runs update
context/          per-client notes for the period (promos, suspensions, stock issues)
scripts/          inventory_flags.py — the shared inventory cleaning and flag rules
skills/
  blueco-weekly-inventory/   Monday inventory report
  blueco-report/             mid-month and end-of-month client report
```

Private repo. No API keys or passwords belong here; connectors handle access.
