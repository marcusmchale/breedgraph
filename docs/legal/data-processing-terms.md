# BreedGraph data processing terms: draft

Status: **draft for the Data Protection Officer and legal office to review and complete.** Not legal advice.
Text in [square brackets] is to be completed. The notes at the end list the questions to settle.

An organisation accepts these terms when it declares its legal entity in BreedGraph, which it must do before recording Person records.
BreedGraph records who accepted which version, and when. Each version needs a version identifier, configured as `DATA_PROCESSING_TERMS_VERSION`, and a published copy at `DATA_PROCESSING_TERMS_URL`.

Version: [version] · Date: [date]

---

## 1. Parties and roles

1. **The Operator**: [the university, legal name and address], which operates BreedGraph.
2. **The Organisation**: the legal entity named in the declaration, acting through the user who accepts these terms, who confirms they are authorised to do so.

For Person records created by teams of the Organisation, the Organisation is the data controller, and the Operator [processes them on its behalf (Art. 28 GDPR) / is a joint controller (Art. 26 GDPR)].

For BreedGraph user accounts, the Operator is the data controller.

## 2. What the Organisation may record

1. Person records hold only what attribution needs: a display name, team affiliations, the lawful basis, and confirmation that the person was informed. The platform does not accept other personal data in Person records.
2. The Organisation records Persons only for people who took part in its research, on the lawful basis it selects for each record, which it has verified applies.
3. The Organisation does not record personal data in research data, such as datasets, files or free-text fields, except as its own policies permit and these terms allow.

## 3. The Organisation's responsibilities

The Organisation:
1. **Informs people** recorded about the record, its purpose, and their rights, for example through its staff privacy notice, and confirms this for each record (Art. 13/14 GDPR).
2. **Decides who can see** its Person records. Releasing records to all registered users or to the public is its decision, and its notices must cover it.
3. **Keeps records accurate**, correcting them when asked.
4. **Handles requests** from people about their data, using the tools BreedGraph provides (correction, erasure, linking to an account), and responds within the time limits of the GDPR. The Operator assists on request.
5. **Keeps its declaration current**: its legal name, and a privacy contact address that reaches the people handling these requests, preferably a role address.
6. **Approves requests to link** a Person record to an account only after confirming the requester's identity.
7. **Controls access** within its teams, granting administrator access only to people who act for it.
8. Tells the Operator without undue delay of any suspected misuse of BreedGraph affecting personal data.

## 4. The Operator's responsibilities

The Operator:
1. Processes Person records only to provide BreedGraph's functions, as documented, and on the Organisation's documented instructions given through those functions.
2. Ensures people with access to the platform's infrastructure are bound by confidentiality.
3. Implements appropriate technical and organisational security measures (Art. 32 GDPR), including access control by team, encrypted connections, password hashing, limits on sign-in attempts, and keeping personal data out of application logs. [Further measures.]
4. Uses the sub-processors listed in Annex A, and informs the Organisation of intended changes, giving it the opportunity to object.
5. Provides tools for the Organisation to meet requests from people: correction, erasure, linking records to accounts and unlinking, and access by the person concerned.
6. **Erasure**: erasing a Person record removes its identifying data and keeps an anonymous record number, so research data stays attributed. Erasures are logged outside the database, by record number only, and applied again if a backup is restored.
7. Notifies the Organisation without undue delay after becoming aware of a personal data breach affecting its Person records (Art. 33 GDPR).
8. Keeps backups for [period] and applies these terms to them.
9. Makes available the information needed to demonstrate compliance, and allows for reviews [on reasonable notice].
10. Does not transfer Person records outside the EEA [except as listed in Annex A, with appropriate safeguards].

## 5. Moving records between organisations

Control of Person records can be transferred to another organisation only if that organisation has declared its legal entity and accepted these terms. The transfer is offered by the Organisation and accepted by the receiving organisation, and is recorded. On acceptance, the receiving organisation becomes the data controller for the records transferred.

## 6. Duration and ending

1. These terms apply from acceptance until the Organisation no longer controls any Person records in BreedGraph.
2. A new declaration accepts the then current version of these terms. Earlier declarations are kept as a record.
3. Before it stops using BreedGraph, the Organisation transfers its Person records to another organisation, or erases them. [What the Operator does with records left behind.]
4. [Changes to these terms: notice, and acceptance of new versions.]

## 7. Liability and governing law

[To be provided by the legal office.]

## Annex A: Sub-processors

| Sub-processor | Purpose | Location |
|---|---|---|
| [Hosting provider] | Hosting the platform and database | [ ] |
| [Email provider] | Sending service emails and messages to contacts | [ ] |
| [Backup storage] | Database backups and the erasure log | [ ] |

## Annex B: Security measures

[Summary of measures, from the Operator's security documentation.]

---

## Notes for the DPO and legal office

1. **Roles**: processor (Art. 28) or joint controllers (Art. 26) for Person records. The platform supports either; the terms need to say which. A consortium agreement may already settle this for some partners.
2. **Click-through acceptance**: whether accepting these terms in BreedGraph, by an organisation admin, is sufficient, or whether partners must also sign.
3. **Authority**: BreedGraph cannot verify that the user declaring the legal entity is authorised to bind it; clause 1.2 relies on their confirmation. Consider whether the Operator should approve declarations.
4. **Liability, governing law, audits** (sections 4.9 and 7).
5. **Records left behind** when an organisation stops using BreedGraph (6.3).
6. **Versioning**: how a change of terms is communicated, and whether organisations must re-accept before continuing to record Persons. BreedGraph currently requires the current version only when declaring.
