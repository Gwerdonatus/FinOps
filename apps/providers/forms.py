from django import forms


class StripeConnectForm(forms.Form):
    secret_key = forms.CharField(
        label="Stripe secret key",
        widget=forms.PasswordInput(render_value=True, attrs={"placeholder": "sk_test_..."}),
    )

    def clean_secret_key(self) -> str:
        key = (self.cleaned_data.get("secret_key") or "").strip()
        if not (key.startswith("sk_test_") or key.startswith("sk_live_")):
            raise forms.ValidationError("Invalid Stripe secret key. Must start with sk_test_ or sk_live_.")
        return key


class ShopifyConnectForm(forms.Form):
    shop_domain = forms.CharField(
        label="Shop domain",
        help_text="e.g. my-store.myshopify.com",
    )
    admin_token = forms.CharField(
        label="Admin API access token",
        widget=forms.PasswordInput(render_value=True),
    )

    def clean_shop_domain(self) -> str:
        domain = (self.cleaned_data.get("shop_domain") or "").strip()
        domain = domain.replace("https://", "").replace("http://", "").strip().strip("/")
        if "." not in domain:
            raise forms.ValidationError("Invalid shop domain (expected something like my-store.myshopify.com).")
        return domain

    def clean_admin_token(self) -> str:
        token = (self.cleaned_data.get("admin_token") or "").strip()
        if len(token) < 10:
            raise forms.ValidationError("Admin token looks too short.")
        return token


class PaystackConnectForm(forms.Form):
    secret_key = forms.CharField(
        label="Paystack secret key",
        widget=forms.PasswordInput(render_value=True, attrs={"placeholder": "sk_test_... or sk_live_..."}),
    )

    def clean_secret_key(self) -> str:
        key = (self.cleaned_data.get("secret_key") or "").strip()
        # Paystack keys typically start with "sk_test_" or "sk_live_"
        if not (key.startswith("sk_test_") or key.startswith("sk_live_")):
            raise forms.ValidationError("Invalid Paystack secret key. Must start with sk_test_ or sk_live_.")
        return key
