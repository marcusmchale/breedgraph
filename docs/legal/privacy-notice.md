# BreedGraph privacy notice: draft

Status: **draft for the Data Protection Officer to review and complete.** Not legal advice.
Text in [square brackets] is to be completed. The notes at the end list the questions to settle.
It describes the system as implemented; see `docs/person.md` for the design.

---

## Who we are

BreedGraph is a research data platform for plant breeding, operated by [team name] at [University of Galway / legal name of the university] ("we").
Partner organisations use BreedGraph to record and share research data.

Contact for questions about this notice or your personal data: [operator contact address].
Data Protection Officer: [DPO name and address].

## Who is responsible for your data

- **Your BreedGraph account**, and how the platform is run: [the university] is the data controller.
- **Person records**, which credit people for their contributions to research: the organisation that recorded you is the data controller.
  Each such organisation has declared its legal name and a privacy contact, shown with the organisation in BreedGraph, and has agreed to our data processing terms.
  We host and process these records for them.

## What we hold and why

### If you have an account

| Data | Why | Kept |
|---|---|---|
| Username, full name, email address | To identify you, and to send you service emails | While your account exists |
| Password, stored as a one-way hash | To sign you in | While your account exists |
| Your team affiliations and access levels, ontology role, default team | To control what you can see and change | While your account exists |
| Records of what you created or changed, and when | To show who contributed what, and for the integrity of research data | As long as the data they relate to |
| Requests you make (affiliations, links to Person records) | To let administrators decide them | Until decided or withdrawn |
| Recent failed sign-in attempts for a username | To protect accounts from password guessing | 1 hour; usernames of locked accounts are also kept in security logs for [period] |
| Sign-in and security tokens, in cookies | To keep you signed in, and against request forgery | Until they expire or you sign out |

[Lawful basis for account data: e.g. Art. 6(1)(b) contract, or 6(1)(e) public task, for providing the platform; 6(1)(f) legitimate interests for security.]

### If you are credited in a Person record

Organisations record the people who took part in research, such as technicians, so that contributions are attributed correctly, whether or not those people have an account.

| Data | Why | Kept |
|---|---|---|
| A display name, and the teams you belong to | To attribute contributions to you | As long as the research data you are credited for |
| The lawful basis, and who recorded you and when | To show why the record is held and by whom | As above |
| Your ORCID iD, if you link it yourself | To identify you unambiguously | Until you remove it |
| The link to your account, if you claim the record | So you can manage it | Until you or an administrator unlink it |

We do not hold contact details, postal addresses or free-text descriptions in Person records.

The organisation that recorded you confirmed that you were informed. The lawful basis is research: [Art. 6(1)(e) public task for the university; 6(1)(f) legitimate interests for other organisations].
We rely on the research provisions of Art. 89 GDPR [and section 42 of the Data Protection Act 2018], including safeguards such as holding only the data needed for attribution.

Who can see a Person record is set by the organisation that controls it: members of its teams, all registered users, or the public. Others may see only that a record exists, by its number.

### If you are invited

When someone invites you, we hold your email address, who invited you, and what the invitation offers (team access, or a Person record to link to your account).
**The invitation, including your email address, is deleted when you register, when it is cancelled, or after [30] days**, whichever comes first.

### Messages to contacts

If your Person record is linked to your account and listed as a contact for a research programme or trial, other registered users can send you a message through BreedGraph.
- BreedGraph sends the message to your account email address. **Senders never see your address.**
- The message includes the sender's name and email address, so you can reply. Replying shares your address with them.
- We do not keep the content of messages. We record that a message was sent, from whom and to whom, in application logs for [period].
- You can remove yourself as a contact at any time.

If you send a message, your name and email address are given to the recipient.

### Other data

- **Research data you upload**, such as datasets and files, is controlled by the teams you upload it for. Do not include personal data in research data unless your organisation permits it.
- **Analysis submissions** are kept for [7] days after their last change.
- **Server logs** record requests to the service, including [IP addresses] in access logs, for [period]. Application logs record actions with account and record numbers, not names or messages.

## Who receives your data

- Other BreedGraph users, as permitted by the access settings above. Team administrators can see who is affiliated to their teams.
- Administrators of the organisation controlling a Person record, including requests to link to it.
- Our service providers: [hosting provider], [email delivery provider], [backup storage].
- [ORCID, only when you link your ORCID iD.]

[Where data is stored, and any transfers outside the EEA.]

## Your rights

You have rights to access, correct and erase your personal data, to restrict or object to its processing, and to data portability, subject to the conditions in the GDPR, including exemptions for research.

In BreedGraph:
- **Your account:** view and change your details in your account settings. [To delete your account, contact us at the address above; this is not yet possible in BreedGraph itself.]
- **A Person record crediting you:** register (or ask to be invited) and ask to link the record to your account. Once linked, you can see it in full, correct your name, unlink it, or **erase it**.
  Erasing removes your name and teams and keeps only an anonymous record number, so research data stays attributed without identifying you. You can also ask the organisation that recorded you, using its privacy contact.
- **Anything else:** contact us, or the privacy contact of the organisation concerned.

We may refuse some requests where the research provisions apply, but we will always explain why. Erasing a Person record is always available, because it keeps the research record intact.

You can complain to the Data Protection Commission (www.dataprotection.ie).

## Backups

Backups of the database are kept for [period] on [the archive server]. If we restore a backup, we apply all erasures made since it was taken before the data is used again, from a log of erased record numbers kept outside the database.

## Changes to this notice

[Date and version. How changes are announced.]

---

## Notes for the DPO

1. **Lawful bases** for account data, and for Person records by the university and by partner organisations.
2. **Art. 89 / section 42 DPA 2018**: whether the research provisions apply as described, and which safeguards to name.
3. **Retention periods** to fill in: security logs, application and access logs, backups.
4. **Account deletion**: not yet implemented in BreedGraph; requests are handled manually until it is. Proposed: deleting an account offers to erase the linked Person record, erasing by default.
5. **Access logs**: whether IP addresses are logged, and for how long, depends on the deployment's web server configuration.
6. **Processors** and where data is hosted.
7. **Public release of Person records**: organisations can release a Person record to the public. The data processing terms make this their decision and require their own notice to cover it.
8. The link from this notice to the **data processing terms** organisations accept (`docs/legal/data-processing-terms.md`).
