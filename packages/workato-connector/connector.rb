# frozen_string_literal: true

# RocketRide custom connector for Workato.
# Sends data to a running RocketRide pipeline webhook and returns its output.
{
  title: 'RocketRide Connector',

  connection: {
    fields: [
      {
        name: 'webhook_url',
        label: 'Webhook URL',
        optional: false,
        hint: 'Webhook URL of your running RocketRide pipeline, e.g. https://host/webhook'
      },
      {
        name: 'auth_key',
        label: 'Authorization key',
        optional: false,
        control_type: 'password',
        hint: 'Public key (pk_...) or private token from the pipeline Endpoint Configuration'
      }
    ],

    authorization: {
      type: 'custom_auth',
      apply: lambda do |connection|
        headers('Authorization' => "Bearer #{connection['auth_key']}")
      end
    },

    base_uri: lambda do |connection|
      connection['webhook_url']
    end
  },

  # No health endpoint on the webhook; a minimal POST validates the URL + auth reach it.
  test: lambda do |_connection|
    post('').payload({})
  end,

  actions: {
    send_to_pipeline: {
      title: 'Send to pipeline',
      subtitle: 'Send data to a RocketRide pipeline and return its output',
      description: "Send data to a running <span class='provider'>RocketRide</span> pipeline",

      input_fields: lambda do |_object_definitions|
        [
          {
            name: 'payload',
            label: 'Payload',
            type: 'object',
            optional: false,
            hint: 'Data sent to the pipeline (matches the lanes the webhook accepts: text, questions, etc.)'
          }
        ]
      end,

      execute: lambda do |_connection, input|
        post('').payload(input['payload'])
      end,

      output_fields: lambda do |_object_definitions|
        [
          { name: 'status' },
          { name: 'data', type: 'object' }
        ]
      end
    }
  }
}
