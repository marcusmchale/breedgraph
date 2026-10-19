# BreedGraph privacy notice: draft

Status: **draft for the Data Protection Officer to confirm.** Not legal advice.
It proposes answers rather than leaving them open; the notes at the end list what to confirm. Text in [square brackets]
is a fact to fill in before publishing.
It describes the system as implemented; see `docs/person.md` for the design and `docs/read-access.md` for who can read what.

When complete, it replaces the text in breedview `public/privacy_notice.md`.
To publish it, copy the notice, from its title to the end of "Changes to this notice", to that file.
breedview renders the file with a simple parser (`composables/system/usePrivacyNotice.js`) that handles headings, bold, italics, `-` bullets and `---` rules only, so the notice has no tables, links or nested lists.

---

# BreedGraph privacy notice

**Last updated: [date]**

## Summary

- BreedGraph is a research data platform for plant breeding, run by the University of Galway. Partner organisations use it to record and share research data.
- The University is responsible for all personal data in BreedGraph: your account, and the records that credit people for research.
- Your email address is not shown to other users.
- People are credited only where signed-in users can see it. Pages open to everyone show no one's name, and there is no public directory of people or organisations.
- You can erase a record that credits you, or ask us to, and you can delete your account at any time.
- BreedGraph sets only the cookies it needs to sign you in and protect your requests. Maps and place searches come from our own server, so using BreedGraph sends nothing from your browser to other companies, unless you choose to link your ORCID iD.

## Who we are

BreedGraph is operated by the University of Galway ("we"). It consists of the BreedGraph API and the BreedView website, hosted at breedgraph.universityofgalway.ie on University infrastructure in Ireland.

Contact for questions about this notice or your personal data: [BreedGraph contact address].

Data Protection Officer: [name and contact address of the University's Data Protection Officer].

## Who is responsible for your data

The University of Galway is the data controller for all personal data in BreedGraph: accounts, the Person records that credit people for research, invitations, messages and logs.

Research data, such as datasets and files, is controlled by the teams that upload it. Teams decide who can see what they control, but the University remains responsible for any personal data in BreedGraph.

## If you have an account

What we hold:

- your username, full name and email address;
- your password, as a one-way hash, never in readable form;
- your team affiliations and access levels (read, write, curate, admin), your default team for new records, and your role in developing the shared ontology;
- requests you make: to join teams, for an ontology role, or to link a Person record to your account;
- records of what you created or changed, and when.

Why: to sign you in, to control what you can see and change, to send you service emails (account verification, password resets, invitations and notices about requests), and to record who contributed what, for the integrity of research data. We do not send marketing emails.

Who sees it:

- Your email address: only you and us.
- Your username and full name: you, and administrators of the teams you belong to or ask to join.
- What you created or changed is shown as the work of the Person record linked to your account, if there is one, to those who can see that record (see below). Otherwise it is not attributed to you by name.

Lawful basis: a task carried out in the public interest (Art. 6(1)(e) GDPR). The University provides BreedGraph as part of its research.

How long: while your account exists. When you delete your account, your username, full name, email address, password and team memberships are removed, and what you contributed stays attributed to an anonymous account number.

### Signing in

- After five failed sign-in attempts within an hour, the username is locked for five minutes. We keep the count of failed attempts for an hour.
- Usernames that get locked are recorded in our application logs, kept for 90 days, so that we can detect password guessing.
- Links in verification and password reset emails expire after 24 hours.

## If you are credited in a Person record

Partner organisations use BreedGraph to record the people who took part in their research, such as technicians and field staff, so that contributions are attributed correctly, whether or not those people have an account. A Person record can be credited as a contributor, with the roles played, or named as a contact, on research programmes, trials, datasets and files.

The person who records you confirms that you took part in the research and that you were told about the record and this notice. They act on the University's behalf.

What a Person record holds:

- a display name, the institution you did the work with, and the teams you belong to;
- confirmation that you were told, and who recorded you and when;
- your ORCID iD, only if you link it yourself;
- the link to your account, if you claim the record.

Person records hold no contact details, postal addresses or free-text descriptions.

Why: to attribute research to the people who did it.

Lawful basis: a task carried out in the public interest (Art. 6(1)(e)), scientific research. We rely on the research provisions of Art. 89 GDPR and section 42 of the Data Protection Act 2018, with safeguards including holding only what attribution needs, showing it only to signed-in users, and letting you erase it at any time.

Who sees it: the teams that control the record decide whether it is shown to their own members only, or to all signed-in users.

- Members of those teams with read access, and you once the record is linked to your account, see the whole record.
- Other signed-in users it is shown to see only what attribution needs: your name, institution and ORCID iD.
- People who are not signed in never see Person records: pages open to everyone show no contributors or contacts.
- BreedGraph has no public directory of people. Signed-in users can search, by name, the records shown to them.

How long: as long as the research data you are credited for. Your ORCID iD is kept until you remove it, and the link to your account until you or an administrator remove it.

### Linking your ORCID iD

To link your ORCID iD to the record linked to your account, you sign in at ORCID, which tells us your iD. ORCID also sends us your name and an access token, which we do not keep.

## If you are invited

When someone invites you, we hold your email address, who invited you, and what the invitation offers (team access, or a Person record to link to your account).

**The invitation, including your email address, is deleted when you register, when it is cancelled, or after 30 days**, whichever comes first.

## Messages to contacts

If the Person record linked to your account is named as a contact for a research programme or trial, signed-in users who can see it can send you a message through BreedGraph.

- BreedGraph passes the message on to your account email address and does not keep it. **Senders never see your address.**
- The message includes the sender's name and email address, so that you can reply. Replying shares your address with them.
- Our application logs record that a message was sent, by account and record number, never its content.
- You can remove yourself as a contact at any time.

If you send a message, your name and email address are given to the recipient.

## Research data

Research data, such as datasets, files and analyses, is controlled by the teams it is uploaded for. It describes plants, samples, locations and measurements, and should not include personal data.

Uploads awaiting processing, and analysis jobs, are kept for 7 days after their last change. Download links expire after 24 hours.

## When you use the website

### Cookies

BreedGraph sets two cookies. Both are needed for the service to work, so they do not need your consent.

- auth_token keeps you signed in, for 7 days or until you sign out.
- csrf_token protects your requests against forgery by other websites, for an hour.

We use no analytics, advertising or tracking cookies.

### Maps and place search

- Maps are drawn from OpenStreetMap data served by our own server.
- When you search for a place on a map, our server asks the Nominatim service of the OpenStreetMap Foundation (United Kingdom) for you. It receives your search, but not your IP address or who you are. Place search is for signed-in users.

### Server logs

- Access logs record requests to the service, including your IP address, and are kept for 30 days.
- Application logs record actions by account and record number, not names, email addresses, searches or message content, and are kept for 90 days.

## Who receives your data

- Other BreedGraph users, as described above.
- Others, where the law requires it.

The University's IT services host the platform and its database, and send its emails. A server of the University's Plant Systems Biology Laboratory keeps the database backups, archives uploaded files and runs analyses. Your data is stored in Ireland.

## Backups

Backups of the database are kept for 90 days on the Plant Systems Biology Laboratory's server. If we restore a backup, we first apply every Person record erasure and account deletion made since it was taken. We do this from a log of the record and account numbers concerned, which is kept outside the database.

## Security

- Connections are encrypted (HTTPS), and cookies are sent only over encrypted connections.
- Access to data is controlled by team, and Person records are never shown to people who are not signed in.
- Passwords are hashed, and sign-in attempts are limited.
- Personal data is kept out of application logs, and error details are not sent to users' browsers.
- Administrative access to servers is restricted, under the University's controls and confidentiality obligations. Only the BreedGraph operator uses the laboratory's server.

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

We will update this notice when BreedGraph or the law changes, and tell registered users of significant changes [by email / when they next sign in].

---

## Notes for the DPO

The design was simplified so that this notice can state its answers. The University is the only data controller,
Person records are never shown to people who are not signed in, and browsers contact no third party. Three points to
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

Before publishing, the operator fills in the contact address (a role address, rather than an individual's), the DPO's
details, and the date.

Other points, for information:
- People are recorded by partner users, who confirm that each person took part and was told about the record and this
  notice (`informed_attestation`). No separate agreement is made with partner organisations.
- Place searches are sent to Nominatim (OpenStreetMap Foundation, UK, which has an adequacy decision) by our server,
  without the user's IP address. Map tiles come from our server.
- The registration form asks users to confirm they have read this notice, not to consent.
