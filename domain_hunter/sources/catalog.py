from __future__ import annotations

# Реальный curated-каталог известных компаний/продуктов. Здесь нет сгенерированных доменов:
# список используется только как быстрый seed, пока сетевые источники парсятся.
CATALOG = {
    "crypto": ["coinbase.com", "kraken.com", "binance.com", "ledger.com", "metamask.io", "coindesk.com", "cointelegraph.com", "chain.link", "etherscan.io", "blockchain.com", "bitstamp.net", "gemini.com", "crypto.com", "okx.com", "bybit.com", "bitfinex.com", "walletconnect.com", "opensea.io", "uniswap.org", "aave.com", "compound.finance", "makerdao.com", "pancakeswap.finance", "curve.fi", "defillama.com", "dune.com", "nansen.ai", "elliptic.co", "chainalysis.com", "fireblocks.com", "anchorage.com", "bitgo.com", "trustwallet.com", "exodus.com", "trezor.io", "ripple.com", "stellar.org", "solana.com", "polygon.technology", "avax.network", "near.org", "cosmos.network", "cardano.org", "tezos.com", "algorand.com", "sui.io", "aptoslabs.com", "consensys.io", "alchemy.com", "infura.io", "moralis.io"],
    "finance": ["wise.com", "revolut.com", "stripe.com", "paypal.com", "squareup.com", "adyen.com", "plaid.com", "robinhood.com", "sofi.com", "intuit.com", "xero.com", "brex.com", "ramp.com", "chime.com", "monzo.com", "n26.com", "klarna.com", "affirm.com", "wealthfront.com", "betterment.com", "etrade.com", "interactivebrokers.com", "fidelity.com", "vanguard.com"],
    "payments": ["stripe.com", "paypal.com", "adyen.com", "checkout.com", "worldpay.com", "payoneer.com", "wise.com", "squareup.com", "braintreepayments.com", "authorize.net", "rapyd.net", "mollie.com", "payu.com", "razorpay.com", "airwallex.com"],
    "banking": ["chase.com", "bankofamerica.com", "wellsfargo.com", "citi.com", "capitalone.com", "monzo.com", "n26.com", "revolut.com", "starlingbank.com", "ally.com", "varomoney.com", "chime.com"],
    "hosting": ["hostinger.com", "godaddy.com", "namecheap.com", "bluehost.com", "siteground.com", "digitalocean.com", "linode.com", "vultr.com", "hetzner.com", "ovhcloud.com", "cloudways.com", "wpengine.com", "kinsta.com", "dreamhost.com", "hostgator.com"],
    "domains": ["namecheap.com", "godaddy.com", "dynadot.com", "porkbun.com", "namesilo.com", "gandi.net", "hover.com", "enom.com", "sedo.com", "dan.com", "afternic.com"],
    "ai": ["openai.com", "anthropic.com", "perplexity.ai", "huggingface.co", "midjourney.com", "stability.ai", "runwayml.com", "replicate.com", "jasper.ai", "copy.ai", "character.ai", "mistral.ai", "cohere.com", "deepmind.google", "scale.com"],
    "vpn": ["nordvpn.com", "expressvpn.com", "surfshark.com", "protonvpn.com", "privateinternetaccess.com", "cyberghostvpn.com", "mullvad.net", "windscribe.com", "tunnelbear.com", "ivacy.com"],
    "education": ["coursera.org", "udemy.com", "edx.org", "khanacademy.org", "duolingo.com", "skillshare.com", "masterclass.com", "codecademy.com", "pluralsight.com", "udacity.com", "futurelearn.com"],
    "health": ["webmd.com", "healthline.com", "mayoclinic.org", "zocdoc.com", "teladoc.com", "goodrx.com", "betterhelp.com", "headspace.com", "calm.com", "onepeloton.com"],
    "shopping": ["amazon.com", "shopify.com", "etsy.com", "ebay.com", "walmart.com", "target.com", "aliexpress.com", "wayfair.com", "bestbuy.com", "shein.com", "zalando.com"],
    "travel": ["booking.com", "airbnb.com", "expedia.com", "tripadvisor.com", "kayak.com", "skyscanner.net", "hotels.com", "agoda.com", "vrbo.com", "trivago.com"],
    "sport": ["espn.com", "nike.com", "adidas.com", "strava.com", "fitbit.com", "underarmour.com", "runtastic.com", "bleacherreport.com", "draftkings.com", "fanduel.com"],
    "business": ["salesforce.com", "hubspot.com", "zoho.com", "slack.com", "notion.so", "atlassian.com", "monday.com", "asana.com", "airtable.com", "docusign.com", "zendesk.com"],
    "email": ["gmail.com", "outlook.com", "proton.me", "mailchimp.com", "sendgrid.com", "mailgun.com", "fastmail.com", "zoho.com", "aweber.com", "constantcontact.com"],
    "cloud": ["aws.amazon.com", "azure.microsoft.com", "cloud.google.com", "digitalocean.com", "cloudflare.com", "oracle.com", "ibm.com", "heroku.com", "vercel.com", "netlify.com", "render.com"],
    "marketing": ["hubspot.com", "semrush.com", "ahrefs.com", "moz.com", "mailchimp.com", "hootsuite.com", "buffer.com", "sproutsocial.com", "canva.com", "marketo.com"],
    "social": ["facebook.com", "instagram.com", "x.com", "linkedin.com", "tiktok.com", "reddit.com", "discord.com", "snapchat.com", "pinterest.com", "telegram.org"],
}

ALIASES = {"payments": "finance", "banking": "finance", "domains": "hosting"}


class Source:
    name = "curated_company_catalog"

    def collect(self, keywords: list[str], limit: int) -> list[str]:
        results: list[str] = []
        for keyword in keywords or ["business"]:
            key = keyword.lower()
            results.extend(CATALOG.get(key, []))
            results.extend(CATALOG.get(ALIASES.get(key, ""), []))
            if len(results) >= limit:
                break
        return results[:limit]
