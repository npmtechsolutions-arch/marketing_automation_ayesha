import uuid

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


async def test_the_workspace_list_carries_the_organization_name(
    client, auth_header, db_session, user_factory, account_factory,
    organization_factory, member_factory,
):
    """So the switcher can group by company without /organizations/.

    An invited collaborator gets a TeamMember row and no OrganizationMember
    row, so GET /organizations/ correctly returns nothing for them. The
    switcher grouped workspaces under organizations and dropped any whose
    organization was missing -- which was every workspace such a person had
    been invited to, i.e. the only one they cared about.
    """
    from app.models.team_member import InvitationStatus, TeamRole

    owner = await user_factory()
    organization = await organization_factory(owner, name="Northwind Agency")
    account = await account_factory(owner, organization=organization)

    guest = await user_factory()
    await member_factory(
        guest, account, role=TeamRole.EDITOR,
        invitation_status=InvitationStatus.ACCEPTED,
    )

    response = await client.get("/api/v1/accounts/", headers=auth_header(guest))

    assert response.status_code == 200, response.text
    [workspace] = response.json()["items"]
    assert workspace["organization_name"] == "Northwind Agency"
    assert workspace["role"] == "editor"

    # And the org list still refuses -- a name is not access.
    orgs = await client.get("/api/v1/organizations/", headers=auth_header(guest))
    assert orgs.json() == []


async def test_the_invitation_token_reaches_someone_who_can_invite(
    client, auth_header, db_session, user_factory, account_factory,
    organization_factory, set_limit,
):
    """The team page needs it to offer "copy invitation link".

    Without it the link exists only in the invite dialog's success state, and
    dismissing that dialog left no way to recover it.
    """
    from app.services import entitlement_service as ent

    owner = await user_factory()
    organization = await organization_factory(owner)
    await set_limit(organization, ent.TEAM_MEMBERS, 10)
    account = await account_factory(owner, organization=organization)

    invited = f"guest-{uuid.uuid4().hex[:8]}@example.com"
    created = await client.post(
        f"/api/v1/accounts/{account.id}/team/invite",
        headers=auth_header(owner),
        json={"email": invited, "role": "editor"},
    )
    assert created.status_code == 201, created.text

    listed = await client.get(
        f"/api/v1/accounts/{account.id}/team/", headers=auth_header(owner)
    )
    pending = [
        m for m in listed.json()["items"] if m["invitation_email"] == invited
    ]
    assert len(pending) == 1
    assert pending[0]["invitation_token"], "owner cannot build the invite link"


async def test_a_role_that_cannot_invite_does_not_receive_the_token(
    client, auth_header, db_session, user_factory, account_factory,
    organization_factory, member_factory, set_limit,
):
    """team.view is held by almost every role; issuing invitations is not.

    Not a live hole -- accept-invite checks the invitation email against the
    caller's own -- but a secret sent to seven roles when one needs it.
    """
    from app.models.team_member import InvitationStatus, TeamRole
    from app.services import entitlement_service as ent

    owner = await user_factory()
    organization = await organization_factory(owner)
    await set_limit(organization, ent.TEAM_MEMBERS, 10)
    account = await account_factory(owner, organization=organization)

    viewer = await user_factory()
    await member_factory(
        viewer, account, role=TeamRole.VIEWER,
        invitation_status=InvitationStatus.ACCEPTED,
    )
    await client.post(
        f"/api/v1/accounts/{account.id}/team/invite",
        headers=auth_header(owner),
        json={"email": f"guest-{uuid.uuid4().hex[:8]}@example.com", "role": "editor"},
    )

    listed = await client.get(
        f"/api/v1/accounts/{account.id}/team/", headers=auth_header(viewer)
    )

    assert listed.status_code == 200
    assert all(m["invitation_token"] is None for m in listed.json()["items"])
