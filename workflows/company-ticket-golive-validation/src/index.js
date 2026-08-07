/**
 * HubSpot workflow custom code action.
 *
 * Enroll on: Companies
 * Purpose:   Compare the Company's "Target Go-Live Date" against the
 *            "Target Go Live Date" on the company's Ticket in the
 *            Onboarding Pipeline, and expose the result as workflow
 *            output fields so a downstream IF/THEN branch can act on it.
 *
 * Required action secret:
 *   PRIVATE_APP_ACCESS_TOKEN - a Private App token with scopes:
 *     crm.objects.companies.read
 *     crm.objects.tickets.read
 *     crm.objects.contacts.read (only if associations require it in your portal)
 *     crm.objects.associations.read (or equivalent association read scope)
 */

const hubspot = require('@hubspot/api-client');

const ONBOARDING_PIPELINE_ID = '751582029'; // "Onboarding Pipeline" on the Ticket object
const COMPANY_GOLIVE_PROPERTY = 'target_golive_date'; // Company: "Target Go-Live Date"
const TICKET_GOLIVE_PROPERTY = 'target_go_live_date'; // Ticket: "Target Go Live Date"

// HubSpot date-only properties are returned as midnight-UTC millisecond
// timestamps. Normalize to YYYY-MM-DD so equal calendar dates always compare
// equal regardless of the exact timestamp/timezone formatting.
const normalizeDate = (value) => (value ? new Date(value).toISOString().slice(0, 10) : null);

exports.main = async (event) => {
  const hubspotClient = new hubspot.Client({ accessToken: process.env.PRIVATE_APP_ACCESS_TOKEN });
  const companyId = event.object.objectId;

  const company = await hubspotClient.crm.companies.basicApi.getById(companyId, [
    COMPANY_GOLIVE_PROPERTY,
  ]);
  const companyGoLiveDate = normalizeDate(company.properties[COMPANY_GOLIVE_PROPERTY]);

  const associations = await hubspotClient.crm.associations.v4.basicApi.getPage(
    'companies',
    companyId,
    'tickets'
  );
  const ticketIds = associations.results.map((result) => result.toObjectId.toString());

  if (ticketIds.length === 0) {
    return buildOutput('NO_TICKET_ASSOCIATED', companyGoLiveDate, null, null);
  }

  const batchRead = await hubspotClient.crm.tickets.batchApi.read({
    inputs: ticketIds.map((id) => ({ id })),
    properties: ['hs_pipeline', TICKET_GOLIVE_PROPERTY],
  });

  const onboardingTickets = batchRead.results.filter(
    (ticket) => ticket.properties.hs_pipeline === ONBOARDING_PIPELINE_ID
  );

  if (onboardingTickets.length === 0) {
    return buildOutput('NO_ONBOARDING_TICKET_FOUND', companyGoLiveDate, null, null);
  }

  // If more than one onboarding ticket is associated, use the most recently created one.
  const ticket = onboardingTickets.sort(
    (a, b) => new Date(b.createdAt) - new Date(a.createdAt)
  )[0];
  const ticketGoLiveDate = normalizeDate(ticket.properties[TICKET_GOLIVE_PROPERTY]);

  let validationResult;
  if (!companyGoLiveDate || !ticketGoLiveDate) {
    validationResult = 'MISSING_DATE';
  } else if (companyGoLiveDate === ticketGoLiveDate) {
    validationResult = 'MATCH';
  } else {
    validationResult = 'MISMATCH';
  }

  return buildOutput(validationResult, companyGoLiveDate, ticketGoLiveDate, ticket.id);
};

function buildOutput(validationResult, companyGoLiveDate, ticketGoLiveDate, onboardingTicketId) {
  return {
    outputFields: {
      validationResult,
      datesMatch: validationResult === 'MATCH',
      companyGoLiveDate,
      ticketGoLiveDate,
      onboardingTicketId,
    },
  };
}
