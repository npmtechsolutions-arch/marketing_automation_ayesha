

async def test_the_invite_link_carries_the_account_id(monkeypatch):
    """Walkthrough find: no invitation could ever be accepted.

    The accept page looks an invitation up at
    ``/accounts/{account_id}/team/invite-info?token=...`` -- the id is in the
    path. The email built ``/accept-invite?token=...`` with no account, so the
    page had nothing to ask with and showed "Missing account or invitation
    token in link". Backend and frontend were each right on their own; nothing
    exercised the contract between them until someone clicked the link.
    """
    from app.services.email_service import EmailService

    sent: dict[str, str] = {}

    async def capture(*, to, subject, html_body, text_body):
        sent["html"] = html_body
        sent["text"] = text_body
        return True

    monkeypatch.setattr(EmailService, "_send", capture)

    await EmailService.send_invitation_email(
        "them@example.com", "Olive", "Workspace", "tok123", "editor",
        "11111111-1111-1111-1111-111111111111",
    )

    body = sent["html"] + sent["text"]
    assert "account=11111111-1111-1111-1111-111111111111" in body
    assert "token=tok123" in body
