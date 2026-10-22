# BreedGraph privacy notice: draft

Status: **draft for the Data Protection Officer to confirm.** Not legal advice.
It proposes answers rather than leaving them open; the notes at the end list what to confirm. Text in [square brackets]
is a fact to fill in before publishing.
It describes the system as implemented; see `docs/person.md` for the design and `docs/read-access.md` for who can read what.

The API serves the published copy, `src/breedgraph/legal/privacy_notice.md` (or the file `PRIVACY_NOTICE_PATH` names),
to the website and to anyone using the API, before they accept the Terms of Use too. When complete, this notice replaces
that copy: to publish it, copy the notice, from its title to the end of "Changes to this notice", to that file, and
restart the API.
breedview renders it with a small markdown renderer (`composables/system/markdown.js`, shared with the Terms of Use and licences) that handles headings, bold, italics, `-` and numbered lists, http, https and mailto links, and `---` rules only, so the notice has no tables or nested lists.

---

# BreedGraph privacy notice

**Last updated: [date]**

## Summary

- BreedGraph is a research data platform for plant breeding, run by the University of Galway. Partner organisations use it to record and share research data.
- The University is responsible for all personal data in BreedGraph: your account, and the records that credit people for research.
- Your email address is not shown to other users.
- People are credited only where signed-in users can see it. Pages open to everyone show no one's name, and there is no public directory of people or organisations.
- You can erase a record that credits you, or ask us to, and you can delete your account at any time.
- BreedGraph sets only the cookies it needs to sign you in, protect your requests and remember that you accepted its Terms of Use and any study licences. Maps and place searches come from our own server, so using BreedGraph sends nothing from your browser to other companies, unless you choose to link your ORCID iD.

## Who we are

BreedGraph is run by the University of Galway ("we"), the data controller for all personal data in it. It consists of the BreedGraph API and the BreedView website, at breedgraph.universityofgalway.ie.

Contact for questions about this notice or your personal data: [BreedGraph contact address].

Data Protection Officer: [name and contact address of the University's Data Protection Officer].

## If you have an account

What we hold:

- your username, full name and email address;
- your password, as a one-way hash, never in readable form;
- your team affiliations and access levels (read, write, curate, admin), your default team for new records, and your role in developing the shared ontology;
- requests you make: to join teams, for an ontology role, or to link a Person record to your account;
- records of what you created or changed, and when.

Why: to sign you in, to control what you can see and change, to record who contributed what, for the integrity of research data, and to send you the emails the service needs, such as account verification, password resets, invitations, replies to your requests and the progress of work you started. We do not send marketing emails.

Who sees it:

- Your email address: only you and us.
- Your username and full name: you, and administrators of the teams you belong to or ask to join.
- What you created or changed is shown as the work of the Person record linked to your account, if there is one, to those who can see that record (see below). Otherwise it is not attributed to you by name.

To detect password guessing, we count failed sign-in attempts, and record in our application logs the usernames locked after repeated failures.

## If you are credited in a Person record

Partner organisations use BreedGraph to record the people who took part in their research, such as technicians and field staff, so that contributions are attributed correctly, whether or not those people have an account. A Person record can be credited as a contributor, with the roles played, or named as a contact, on research programmes, trials, datasets and files.

The person who records you confirms that you took part in the research and that you were told about the record and this notice. They act on the University's behalf.

What a Person record holds:

- a display name, the institution you did the work with, and the teams you belong to;
- confirmation that you were told, and who recorded you and when;
- your ORCID iD, only if you link it yourself;
- the link to your account, if you claim the record.

It holds no contact details, postal addresses or free-text descriptions.

Why: to attribute research to the people who did it.

Who sees it: the teams that control the record decide whether it is shown to their own members only, or to all signed-in users.

- Members of those teams with read access, and you once the record is linked to your account, see the whole record.
- Other signed-in users it is shown to see only what attribution needs: your name, institution and ORCID iD.
- People who are not signed in never see Person records. Signed-in users can search, by name, the records shown to them.

To link your ORCID iD, you sign in at ORCID, which tells us your iD. ORCID also sends us your name and an access token, which we do not keep.

## If you are invited

When someone invites you, we hold your email address, who invited you, and what the invitation offers: team access, or a Person record to link to your account.

## Messages to contacts

If the Person record linked to your account is named as a contact for a research programme or trial, signed-in users who can see it can send you a message through BreedGraph.

- BreedGraph passes the message on to your account email address and does not keep it. **Senders never see your address.**
- The message includes the sender's name and email address, so that you can reply. Replying shares your address with them.
- You can remove yourself as a contact at any time.

If you send a message, your name and email address are given to the recipient.

## Research data

Research data, such as datasets, files and analyses, is controlled by the teams it is uploaded for. It describes plants, samples, locations and measurements, and should not include personal data.

## When you use the website

### Cookies

BreedGraph sets three kinds of cookie. All are needed for the service to work, so they do not need your consent.

- auth_token keeps you signed in, for 7 days or until you sign out.
- csrf_token protects your requests against forgery by other websites, for an hour.
- acceptances remembers that you accepted the Terms of Use and the licences of the studies whose data you opened: which versions, by their fingerprints, and, if you are signed in, your account number, so that it holds for your account alone. It lasts 7 days if you are not signed in and a year if you are, and is set again when you accept something more. We keep no record of what you accepted.

We use no analytics, advertising or tracking cookies.

### Maps and place search

- Maps are served from our own server. To prepare detailed maps of an area, our server downloads public map data, and sends nothing about you.
- When you search for a place on a map, our server asks the Nominatim service of the OpenStreetMap Foundation (United Kingdom) for you. It receives your search, but not your IP address or who you are.

### Server logs

- Access logs record requests to the service, including your IP address.
- Application logs record actions by account and record number, not names, email addresses, searches or message content.

## Lawful basis

We process personal data in BreedGraph as a task carried out in the public interest (Art. 6(1)(e) GDPR), as the University provides BreedGraph as part of its research. For Person records, which serve scientific research, we also rely on the research provisions of Art. 89 GDPR and section 42 of the Data Protection Act 2018, with safeguards including holding only what attribution needs, showing it only to signed-in users, and letting you erase it at any time.

## How long we keep it

- Your account: while it exists. When you delete it, your username, full name, email address, password and team memberships are removed, and what you contributed stays attributed to an anonymous account number.
- Person records: as long as the research data they credit. An ORCID iD is kept until you remove it, and the link to your account until you or an administrator remove it.
- Invitations, including the email address: until you register or the invitation is cancelled, and at most 30 days.
- Counts of failed sign-in attempts: one hour.
- Uploads awaiting processing, and analysis jobs: 7 days after their last change.
- Access logs: 30 days. Application logs: 90 days.
- Backups of the database: 90 days.

## Who receives your data, and where it is kept

- Other BreedGraph users, as described above.
- Others, where the law requires it.

The University's IT services host BreedGraph and its database, and send its emails. A server of the University's Plant Systems Biology Laboratory keeps the database backups, archives uploaded files and runs analyses. Backups and archived files are encrypted before they are copied to that server, which holds no key to read them. Your data is stored in Ireland.

Some users work for partner organisations outside the European Economic Area (EEA), so what they can see, as described above, is transferred outside the EEA. These transfers are protected by [the safeguard, such as standard contractual clauses, and how to get a copy of it].

If we restore a backup, we first apply every Person record erasure and account deletion made since it was taken, from a log of the record and account numbers concerned, kept outside the database.

## Security

- Connections are encrypted (HTTPS), and cookies are sent only over encrypted connections.
- Access to data is controlled by team.
- Passwords are hashed, and sign-in attempts are limited.
- Administrative access to the servers is restricted to the people who run BreedGraph, under the University's controls and confidentiality obligations.

## Your rights

You have rights to access, correct and erase your personal data, to restrict or object to its processing, and to data portability, subject to the conditions in the GDPR, including exemptions for research.

In BreedGraph:

- **Your account**: change your username, full name, email address or password, or delete your account, in your account settings. When you delete your account, you are asked whether to erase the Person record linked to it as well, which is the default.
- **A Person record crediting you**: if you have an account, ask to link the record to your account. Administrators of the teams that control it decide the request, after confirming who you are. Once linked, you can see the record in full, correct your name, link your ORCID iD, unlink the record, or **erase it**.
- **If you have no account**, contact us. Once we have confirmed who you are, we can erase the record for you, or invite you to register and link it, so you can manage it yourself.
- **Erasing a Person record** removes your name, institution, teams and ORCID iD and keeps only an anonymous record number, so research data stays attributed without identifying you.
- **Anything else**: contact us.

We may refuse some requests where the research provisions apply, and we will always explain why. Erasing a Person record is always available, because it keeps the research record intact.

You can complain to the Data Protection Commission (www.dataprotection.ie).

## Changes to this notice

We will update this notice when BreedGraph or the law changes, and tell registered users of significant changes by email.

---

## Notes for the DPO

The design was simplified so that this notice can state its answers. The University is the only data controller,
Person records are never shown to people who are not signed in, and browsers contact no third party. Four points to
confirm:

1. **Lawful basis and research safeguards.** Public task (Art. 6(1)(e)) for everything, accounts and security logging
   included, as legitimate interests is not available to a public authority for its tasks. For Person records, the
   research provisions of Art. 89 and section 42 of the Data Protection Act 2018, with the safeguards named in the
   notice: only what attribution needs, shown only to signed-in users, erasure at any time, and record and account
   numbers in logs rather than names.
2. **Retention periods.** Access logs 30 days; application logs, including security warnings, 90 days; backups 90
   days; invitations 30 days; uploads and analysis jobs 7 days; failed sign-in counts 1 hour. Accounts while they
   exist; Person records as long as the research data they are credited for. The erasure log holds only record and
   account numbers, and is kept indefinitely so that restores stay correct.
3. **Records.** Whether BreedGraph needs a data protection impact assessment, or an entry in the University's record
   of processing activities, and what you need from us for either.
4. **Transfers outside the EEA.** Some partner users are outside the EEA. They see what the notice describes: the
   names, institutions and ORCID iDs in Person records shown to them, the usernames and full names of their team
   members and applicants, and the names and email addresses of people who message them. Which safeguard covers this
   (Art. 13(1)(f)): standard contractual clauses with the partner organisations, or the project's consortium agreement
   if it covers it.

Before publishing, the operator fills in the contact address (a role address, rather than an individual's), the DPO's
details, the safeguard for transfers outside the EEA, and the date.

Other points, for information:
- People are recorded by partner users, who confirm that each person took part and was told about the record and this
  notice (`informed_attestation`). No separate agreement is made with partner organisations.
- Place searches are sent to Nominatim (OpenStreetMap Foundation, UK, which has an adequacy decision) by our server,
  without the user's IP address. Map tiles come from our server, which fetches them from Protomaps' builds, with
  country outlines from geoBoundaries, sending no personal data or site coordinates.
- The registration form asks users to confirm they have read this notice, not to consent.
