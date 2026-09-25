<?php
// Contact form endpoint for robotmonaco.com. The form posts here and expects {"ok":true} back.
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'method']);
    exit;
}

const TO      = 'info@robotmonaco.com';
const FROM    = 'no-reply@robotmonaco.com';   // a mailbox on our own domain, so SPF and DMARC pass
const SUBJECT = 'Website enquiry';

/** Header fields must never carry a line break, or a sender could inject extra headers. */
function header_safe(string $v): string {
    return trim(str_replace(["\r", "\n", "\0"], ' ', $v));
}

$lines = [];
foreach ($_POST as $key => $value) {
    if (!is_string($value) || $value === '') {
        continue;
    }
    $key = header_safe((string)$key);
    $lines[] = $key . ': ' . trim($value);
}

if (!$lines) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'empty']);
    exit;
}

$replyTo = filter_var(trim((string)($_POST['E-mail'] ?? '')), FILTER_VALIDATE_EMAIL);
$name    = header_safe((string)($_POST['Name'] ?? ''));

$body = implode("\n", $lines)
      . "\n\n---\n"
      . 'Sent from ' . header_safe((string)($_SERVER['HTTP_HOST'] ?? 'robotmonaco.com'))
      . ' on ' . gmdate('Y-m-d H:i') . " UTC\n";

$headers = [
    'From: ROBOTMONACO <' . FROM . '>',
    'Content-Type: text/plain; charset=utf-8',
    'X-Mailer: robotmonaco-form',
];
if ($replyTo) {
    $headers[] = 'Reply-To: ' . ($name !== '' ? $name . ' <' . $replyTo . '>' : $replyTo);
}

$subject = SUBJECT . ($name !== '' ? ' from ' . $name : '');
$sent = @mail(TO, '=?UTF-8?B?' . base64_encode($subject) . '?=', $body, implode("\r\n", $headers));

if (!$sent) {
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'send']);
    exit;
}

echo json_encode(['ok' => true]);
