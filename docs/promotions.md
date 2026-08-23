# Promotions operations

Promotion campaigns are persisted in the database. Application startup creates
missing promotion tables and indexes, but never prepares or sends a campaign.

## Scheduled delivery

Run the due-campaign processor periodically from the backend directory:

```sh
python -m app.workers.promotion_worker
```

For local development, invoke it manually after a campaign becomes due. In
production, run it from cron or the platform scheduler (once per minute is a
reasonable default). Multiple overlapping invocations are safe: each campaign
is claimed with a conditional database update before provider calls begin, and
network calls are not made inside the claim transaction.

## WhatsApp template

The named marketing template and language must already be approved in WhatsApp
Manager. Body variables are supplied in this order:

1. client name
2. campaign headline
3. offer text
4. coupon code
5. expiration date (`YYYY-MM-DD` in UTC)
6. business name

If a flyer is present, the adapter supplies it as an image-header link. Meta
must be able to fetch that URL. Local media URLs are suitable for dashboard
preview and fake-provider testing only; production should replace the local
storage adapter with object storage that provides a public HTTPS URL.

Provider acceptance records a recipient as `submitted`. Only Meta webhook
events advance it to `sent`, `delivered`, or `read`.
