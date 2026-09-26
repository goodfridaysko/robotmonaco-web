<?php
// Contact form endpoint for robotmonaco.com. The form posts here and expects {"ok":true} back.
//
// Delivery goes through authenticated SMTP, not mail(). The host accepts mail() and returns true
// while the message never leaves the machine, so enquiries were being lost silently. SMTP either
// delivers or says why.
//
// Credentials live in mail.ini, one directory ABOVE the web root, so it is never served:
//
//     host = smtp.websupport.sk
//     port = 465
//     user = no-reply@robotmonaco.com
//     pass = ...
//
// Without that file the endpoint answers {"ok":false,"error":"config"} rather than pretending to
// have sent something.
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'method']);
    exit;
}

const TO        = 'info@robotmonaco.com';
const FROM      = 'no-reply@robotmonaco.com';   // a mailbox on our own domain, so SPF and DMARC pass
const SUBJECT   = 'Website enquiry';
const DIAG_COPY = 'juraj@goodfridays.sk';       // TEMPORARY while delivery is being confirmed; '' switches it off

/** Header fields must never carry a line break, or a sender could inject extra headers. */
function header_safe(string $v): string {
    return trim(str_replace(["\r", "\n", "\0"], ' ', $v));
}

function fail(string $code, string $detail = ''): void {
    if ($detail !== '') {
        error_log('robotmonaco form: ' . $detail);
    }
    http_response_code($code === 'empty' ? 400 : 500);
    echo json_encode(['ok' => false, 'error' => $code]);
    exit;
}

/**
 * Speak SMTP to the mailbox the site owns. Returns '' on success, or the step that went wrong.
 * Deliberately small: one connection, one message, no queueing, no attachments.
 */
function smtp_send(array $cfg, string $from, array $rcpt, string $message): string {
    $port = (int)($cfg['port'] ?? 465);
    $host = ($port === 465 ? 'ssl://' : '') . $cfg['host'];
    $sock = @stream_socket_client("$host:$port", $errno, $errstr, 20);
    if (!$sock) {
        return "connect: $errstr ($errno)";
    }
    stream_set_timeout($sock, 20);

    $read = function () use ($sock): string {
        $out = '';
        while (($line = fgets($sock, 2048)) !== false) {
            $out .= $line;
            if (strlen($line) < 4 || $line[3] !== '-') {   // the last line of a reply has a space, not a dash
                break;
            }
        }
        return $out;
    };
    // Every SMTP reply opens with a three digit code; 2xx and 3xx mean carry on.
    $say = function (string $cmd, string $expect) use ($sock, $read): string {
        if ($cmd !== '') {
            fwrite($sock, $cmd . "\r\n");
        }
        $reply = $read();
        return str_starts_with($reply, $expect) ? '' : trim($cmd === '' ? $reply : "$cmd -> $reply");
    };

    $steps = [['', '220']];
    if ($port !== 465) {                                   // 587: upgrade the plain connection first
        $steps[] = ['EHLO robotmonaco.com', '250'];
        $steps[] = ['STARTTLS', '220'];
    }
    foreach ($steps as [$cmd, $expect]) {
        if ($err = $say($cmd, $expect)) {
            fclose($sock);
            return $err;
        }
    }
    if ($port !== 465 && !@stream_socket_enable_crypto($sock, true, STREAM_CRYPTO_METHOD_TLS_CLIENT)) {
        fclose($sock);
        return 'starttls: the connection could not be secured';
    }

    $conversation = [
        ['EHLO robotmonaco.com', '250'],
        ['AUTH LOGIN', '334'],
        [base64_encode((string)$cfg['user']), '334'],
        [base64_encode((string)$cfg['pass']), '235'],
        ['MAIL FROM:<' . $from . '>', '250'],
    ];
    foreach ($rcpt as $one) {
        $conversation[] = ['RCPT TO:<' . $one . '>', '250'];
    }
    $conversation[] = ['DATA', '354'];
    // A line of its own containing only a dot ends the message, so any such line in the body is doubled.
    $conversation[] = [preg_replace('/^\./m', '..', $message) . "\r\n.", '250'];
    $conversation[] = ['QUIT', '221'];

    foreach ($conversation as [$cmd, $expect]) {
        if ($err = $say($cmd, $expect)) {
            fclose($sock);
            // Never let the password reach a log line.
            return str_contains($err, 'AUTH') || $expect === '334' || $expect === '235'
                ? 'auth: the mailbox refused these credentials'
                : $err;
        }
    }
    fclose($sock);
    return '';
}

$lines = [];
foreach ($_POST as $key => $value) {
    if (!is_string($value) || $value === '') {
        continue;
    }
    $lines[] = header_safe((string)$key) . ': ' . trim($value);
}
if (!$lines) {
    fail('empty');
}

$replyTo = filter_var(trim((string)($_POST['E-mail'] ?? '')), FILTER_VALIDATE_EMAIL);
$name    = header_safe((string)($_POST['Name'] ?? ''));

$body = implode("\n", $lines)
      . "\n\n---\n"
      . 'Sent from ' . header_safe((string)($_SERVER['HTTP_HOST'] ?? 'robotmonaco.com'))
      . ' on ' . gmdate('Y-m-d H:i') . " UTC\n";

$recipients = [TO];
$headers = [
    'Date: ' . gmdate('D, d M Y H:i:s') . ' +0000',
    'From: ROBOTMONACO <' . FROM . '>',
    'To: ' . TO,
    'Subject: =?UTF-8?B?' . base64_encode(SUBJECT . ($name !== '' ? ' from ' . $name : '')) . '?=',
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=utf-8',
    'Content-Transfer-Encoding: 8bit',
    'Message-ID: <' . bin2hex(random_bytes(12)) . '@robotmonaco.com>',
    'X-Mailer: robotmonaco-form',
];
if (DIAG_COPY !== '') {
    $headers[] = 'Cc: ' . DIAG_COPY;
    $recipients[] = DIAG_COPY;
}
if ($replyTo) {
    $headers[] = 'Reply-To: ' . ($name !== '' ? $name . ' <' . $replyTo . '>' : $replyTo);
}

$ini = __DIR__ . '/../mail.ini';
if (!is_readable($ini) || !($cfg = @parse_ini_file($ini)) || empty($cfg['host']) || empty($cfg['user'])) {
    fail('config', 'mail.ini is missing or incomplete, so nothing was sent');
}

$message = implode("\r\n", $headers) . "\r\n\r\n" . str_replace("\n", "\r\n", $body);
if ($err = smtp_send($cfg, FROM, $recipients, $message)) {
    fail('send', 'SMTP refused the message: ' . $err);
}

echo json_encode(['ok' => true]);
