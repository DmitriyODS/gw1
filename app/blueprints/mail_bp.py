import imaplib
import smtplib
import ssl
import email
import email.header
import email.utils
import re
import time
import io
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from flask import (Blueprint, render_template, jsonify, request,
                   current_app, send_file)
from flask_login import login_required, current_user

mail_bp = Blueprint('mail', __name__)

# ── Simple TTL cache ──────────────────────────────────────────────────────────
_cache: dict = {}

def _cache_get(key: str, ttl: int = 300):
    entry = _cache.get(key)
    if entry and time.time() - entry[1] < ttl:
        return entry[0]
    return None

def _cache_set(key: str, val):
    _cache[key] = (val, time.time())

def _cache_clear():
    _cache.clear()


# ── SSL context ───────────────────────────────────────────────────────────────

def _ssl_ctx():
    cfg = current_app.config
    ctx = ssl.create_default_context()
    if not cfg.get('MAIL_VERIFY_SSL', False):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ── IMAP ──────────────────────────────────────────────────────────────────────

def _user_mail_creds():
    """Return (mail_user, mail_password) — per-user if set, else global config."""
    from flask_login import current_user
    cfg = current_app.config
    if current_user.is_authenticated and current_user.mail_user:
        return current_user.mail_user, (current_user.mail_password or cfg['MAIL_PASSWORD'])
    return cfg['MAIL_USER'], cfg['MAIL_PASSWORD']


def _imap_connect():
    cfg = current_app.config
    mail_user, mail_pass = _user_mail_creds()
    conn = imaplib.IMAP4_SSL(cfg['MAIL_IMAP_HOST'], cfg['MAIL_IMAP_PORT'],
                              ssl_context=_ssl_ctx())
    conn.login(mail_user, mail_pass)
    return conn


def _imap_folder(folder: str) -> str:
    """Map logical folder name to actual IMAP folder."""
    if folder == 'sent':
        return current_app.config.get('MAIL_SENT_FOLDER', 'Sent')
    return current_app.config.get('MAIL_INBOX_FOLDER', 'info.kf')


# ── Header / date helpers ─────────────────────────────────────────────────────

def _decode_hdr(value) -> str:
    if not value:
        return ''
    parts = []
    for chunk, charset in email.header.decode_header(value):
        if isinstance(chunk, bytes):
            try:
                parts.append(chunk.decode(charset or 'utf-8', errors='replace'))
            except (LookupError, UnicodeDecodeError):
                parts.append(chunk.decode('utf-8', errors='replace'))
        else:
            parts.append(str(chunk))
    return ''.join(parts)


def _parse_date(date_str: str) -> str:
    try:
        tup = email.utils.parsedate_tz(date_str)
        if tup:
            ts  = email.utils.mktime_tz(tup)
            dt  = datetime.utcfromtimestamp(ts)
            dt += timedelta(hours=current_app.config.get('TZ_OFFSET_HOURS', 3))
            return dt.strftime('%d.%m.%Y %H:%M')
    except Exception:
        pass
    return date_str[:16] if date_str else ''


def _parse_date_long(date_str: str) -> str:
    months = ['января','февраля','марта','апреля','мая','июня',
              'июля','августа','сентября','октября','ноября','декабря']
    try:
        tup = email.utils.parsedate_tz(date_str)
        if tup:
            ts  = email.utils.mktime_tz(tup)
            dt  = datetime.utcfromtimestamp(ts)
            dt += timedelta(hours=current_app.config.get('TZ_OFFSET_HOURS', 3))
            return f'{dt.day} {months[dt.month-1]} {dt.year}, {dt.strftime("%H:%M")}'
    except Exception:
        pass
    return date_str


# ── MIME body / attachment helpers ────────────────────────────────────────────

def _extract_body(msg) -> tuple:
    html_body = text_body = None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp  = str(part.get('Content-Disposition', ''))
            if 'attachment' in disp:
                continue
            charset = part.get_content_charset() or 'utf-8'
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                decoded = payload.decode(charset, errors='replace')
            except (LookupError, UnicodeDecodeError):
                try:
                    decoded = payload.decode('utf-8', errors='replace')
                except Exception:
                    continue
            except Exception:
                continue
            if ctype == 'text/html' and html_body is None:
                html_body = decoded
            elif ctype == 'text/plain' and text_body is None:
                text_body = decoded
    else:
        charset = msg.get_content_charset() or 'utf-8'
        try:
            payload = msg.get_payload(decode=True)
            decoded = payload.decode(charset, errors='replace') if payload else ''
        except Exception:
            decoded = str(msg.get_payload())
        if msg.get_content_type() == 'text/html':
            html_body = decoded
        else:
            text_body = decoded
    return html_body, text_body


def _extract_attachments(msg) -> list:
    result = []
    if msg.is_multipart():
        for part in msg.walk():
            disp = str(part.get('Content-Disposition', ''))
            if 'attachment' not in disp:
                continue
            fname = part.get_filename()
            if fname:
                fname = _decode_hdr(fname)
                payload = part.get_payload(decode=True) or b''
                result.append({'name': fname, 'size': len(payload)})
    return result


def _parse_message_headers(raw: bytes, uid: str) -> dict:
    msg = email.message_from_bytes(raw)
    return {
        'uid':     uid,
        'from':    _decode_hdr(msg.get('From', '')),
        'subject': _decode_hdr(msg.get('Subject', '')) or '(без темы)',
        'date':    _parse_date(msg.get('Date', '')),
        'to':      _decode_hdr(msg.get('To', '')),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@mail_bp.route('/mail')
@login_required
def inbox():
    return render_template('mail/inbox.html',
        from_email=current_app.config.get('MAIL_FROM_EMAIL', ''),
        from_name=current_app.config.get('MAIL_FROM_NAME', ''),
    )


@mail_bp.route('/mail/list')
@login_required
def mail_list():
    folder  = request.args.get('folder', 'inbox')   # 'inbox' | 'sent'
    page    = request.args.get('page', 1, type=int)
    per_pg  = 30
    refresh = request.args.get('refresh', '0') == '1'
    cache_key = f'mail_list_{current_user.id}_{folder}'

    if not refresh:
        cached = _cache_get(cache_key, ttl=120)
        if cached is not None:
            start = (page - 1) * per_pg
            return jsonify({
                'messages': cached[start:start + per_pg],
                'total': len(cached), 'page': page,
                'has_more': start + per_pg < len(cached),
                'from_cache': True,
            })

    try:
        conn        = _imap_connect()
        imap_folder = _imap_folder(folder)

        # SELECT folder; if sent folder not found — try common alternatives
        status, data = conn.select(f'"{imap_folder}"')
        if status != 'OK':
            for alt in ['Sent Items', 'Sent Messages', 'Отправленные', 'INBOX.Sent']:
                status, data = conn.select(f'"{alt}"')
                if status == 'OK':
                    imap_folder = alt
                    break
            if status != 'OK':
                conn.logout()
                return jsonify({'error': f'Папка «{imap_folder}» не найдена на сервере'}), 500

        # Both inbox (info.kf) and sent: read all messages from the folder
        _, sdata = conn.uid('search', None, 'ALL')
        uids = set(sdata[0].split()) if sdata and sdata[0] else set()

        all_uids = sorted(uids, key=lambda x: int(x.decode()), reverse=True)[:300]

        messages = []
        if all_uids:
            uid_str = b','.join(all_uids).decode()
            _, fdata = conn.uid(
                'fetch', uid_str,
                '(UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE TO)])'
            )
            i = 0
            while i < len(fdata):
                item = fdata[i]
                if isinstance(item, tuple):
                    meta = item[0].decode() if isinstance(item[0], bytes) else str(item[0])
                    um = re.search(r'UID (\d+)', meta)
                    fm = re.search(r'FLAGS \(([^)]*)\)', meta)
                    if um:
                        uid_val = um.group(1)
                        flags   = fm.group(1) if fm else ''
                        hdr     = _parse_message_headers(item[1], uid_val)
                        hdr['unread'] = '\\Seen' not in flags
                        messages.append(hdr)
                i += 1

        conn.logout()
        _cache_set(cache_key, messages)

        start = (page - 1) * per_pg
        return jsonify({
            'messages': messages[start:start + per_pg],
            'total': len(messages), 'page': page,
            'has_more': start + per_pg < len(messages),
            'from_cache': False,
        })


    except imaplib.IMAP4.error as e:
        return jsonify({'error': f'Ошибка IMAP: {e}'}), 500
    except Exception as e:
        return jsonify({'error': f'Ошибка подключения: {e}'}), 500


@mail_bp.route('/mail/message/<uid>')
@login_required
def get_message(uid):
    folder    = request.args.get('folder', 'inbox')
    cache_key = f'msg_{current_user.id}_{folder}_{uid}'
    cached    = _cache_get(cache_key, ttl=3600)
    if cached:
        return jsonify(cached)

    try:
        conn        = _imap_connect()
        imap_folder = _imap_folder(folder)
        status, _   = conn.select(f'"{imap_folder}"')
        if status != 'OK':
            conn.logout()
            return jsonify({'error': f'Папка «{imap_folder}» не найдена'}), 404

        _, data = conn.uid('fetch', uid, '(RFC822)')
        if not data or not data[0]:
            conn.logout()
            return jsonify({'error': 'Письмо не найдено'}), 404

        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        html_body, text_body = _extract_body(msg)
        attachments          = _extract_attachments(msg)

        # Mark as read (only inbox)
        if folder == 'inbox':
            conn.uid('store', uid, '+FLAGS', '\\Seen')
            # Update list cache unread flag
            lkey = f'mail_list_{current_user.id}_inbox'
            if lkey in _cache:
                for m in _cache[lkey][0]:
                    if m['uid'] == uid:
                        m['unread'] = False

        conn.logout()

        result = {
            'uid':      uid,
            'folder':   folder,
            'from':     _decode_hdr(msg.get('From', '')),
            'subject':  _decode_hdr(msg.get('Subject', '')) or '(без темы)',
            'date':     _parse_date_long(msg.get('Date', '')),
            'to':       _decode_hdr(msg.get('To', '')),
            'cc':       _decode_hdr(msg.get('Cc', '')),
            'reply_to': _decode_hdr(msg.get('Reply-To', '')),
            'html_body':  html_body,
            'text_body':  text_body,
            'attachments': attachments,
        }
        _cache_set(cache_key, result)
        return jsonify(result)

    except imaplib.IMAP4.error as e:
        return jsonify({'error': f'Ошибка IMAP: {e}'}), 500
    except Exception as e:
        return jsonify({'error': f'Ошибка: {e}'}), 500


@mail_bp.route('/mail/attachment/<uid>/<int:part_index>')
@login_required
def download_attachment(uid, part_index):
    folder      = request.args.get('folder', 'inbox')
    imap_folder = _imap_folder(folder)
    try:
        conn = _imap_connect()
        conn.select(f'"{imap_folder}"')
        _, data = conn.uid('fetch', uid, '(RFC822)')
        conn.logout()
    except Exception as e:
        return f'Ошибка: {e}', 500

    if not data or not data[0]:
        return 'Не найдено', 404

    msg = email.message_from_bytes(data[0][1])
    idx = 0
    if msg.is_multipart():
        for part in msg.walk():
            if 'attachment' not in str(part.get('Content-Disposition', '')):
                continue
            if idx == part_index:
                fname = _decode_hdr(part.get_filename() or f'file_{idx}')
                return send_file(io.BytesIO(part.get_payload(decode=True) or b''),
                                 as_attachment=True, download_name=fname)
            idx += 1
    return 'Не найдено', 404


@mail_bp.route('/mail/send', methods=['POST'])
@login_required
def send_mail():
    to_addr = request.form.get('to', '').strip()
    cc_addr = request.form.get('cc', '').strip()
    subject = request.form.get('subject', '').strip()
    body    = request.form.get('body', '').strip()

    if not to_addr:
        return jsonify({'error': 'Укажите получателя'}), 400
    if not subject:
        return jsonify({'error': 'Укажите тему письма'}), 400

    cfg       = current_app.config
    mail_user, mail_pass = _user_mail_creds()
    smtp_host = cfg.get('MAIL_SMTP_HOST', 'mail.bmstu.ru')
    smtp_port = cfg.get('MAIL_SMTP_PORT', 465)
    smtp_mode = cfg.get('MAIL_SMTP_MODE', 'ssl')
    # Derive from_email from per-user login if set, else use global config
    if current_user.mail_user:
        imap_host = cfg.get('MAIL_IMAP_HOST', 'mail.bmstu.ru')
        domain    = imap_host.replace('mail.', '', 1)
        from_email = f'{mail_user}@{domain}'
        from_name  = current_user.full_name
    else:
        from_email = cfg.get('MAIL_FROM_EMAIL', 'info.kf@bmstu.ru')
        from_name  = cfg.get('MAIL_FROM_NAME', '')

    signature_html = (
        '<br><br>'
        '<div style="font-size:13px;color:#666;border-top:1px solid #e0e0e0;'
        'padding-top:12px;margin-top:12px;line-height:1.6;">'
        'С уважением,<br>'
        '<strong>Управление информационной политики МГТУ им.&nbsp;Н.Э.&nbsp;Баумана</strong><br>'
        'Отдел региональных коммуникаций (Калуга)<br>'
        'Моб.:&nbsp;+7&nbsp;(991)&nbsp;328-29-64,&nbsp;+7&nbsp;(910)&nbsp;912-52-99<br>'
        '<a href="https://kf.bmstu.ru" style="color:#006CDC;">kf.bmstu.ru</a>'
        '&nbsp;|&nbsp;info.kf@bmstu.ru'
        '</div>'
    )

    html_body = body.replace('\n', '<br>') + signature_html
    files     = request.files.getlist('attachments')
    has_att   = any(f.filename for f in files)

    if has_att:
        outer = MIMEMultipart('mixed')
        outer['From']    = f'{from_name} <{from_email}>'
        outer['To']      = to_addr
        if cc_addr: outer['Cc'] = cc_addr
        outer['Subject'] = subject
        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(html_body, 'html', 'utf-8'))
        outer.attach(alt)
        for f in files:
            if not f.filename: continue
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment',
                            filename=('utf-8', '', f.filename))
            outer.attach(part)
        msg = outer
    else:
        msg = MIMEMultipart('alternative')
        msg['From']    = f'{from_name} <{from_email}>'
        msg['To']      = to_addr
        if cc_addr: msg['Cc'] = cc_addr
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    recipients = [to_addr] + ([cc_addr] if cc_addr else [])

    try:
        ctx = _ssl_ctx()
        if smtp_mode == 'starttls':
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=15)

        with server:
            server.login(mail_user, mail_pass)
            # envelope FROM must be a bare address (no "Name <>" wrapper)
            server.sendmail(from_email, recipients, msg.as_bytes())

        # Invalidate sent cache so new message appears
        _cache.pop(f'mail_list_{current_user.id}_sent', None)
        return jsonify({'success': True})

    except smtplib.SMTPAuthenticationError:
        return jsonify({'error': 'Ошибка авторизации SMTP — проверьте логин/пароль'}), 500
    except smtplib.SMTPConnectError as e:
        return jsonify({'error': f'Не удалось подключиться к SMTP: {e}'}), 500
    except smtplib.SMTPException as e:
        return jsonify({'error': f'Ошибка SMTP: {e}'}), 500
    except Exception as e:
        return jsonify({'error': f'Ошибка отправки: {e}'}), 500


@mail_bp.route('/mail/refresh', methods=['POST'])
@login_required
def refresh_mail():
    _cache_clear()
    return jsonify({'success': True})


@mail_bp.route('/mail/test')
@login_required
def test_connection():
    """Diagnostic endpoint — доступен только для can_manage."""
    if not current_user.can_manage:
        return jsonify({'error': 'Нет прав'}), 403

    cfg    = current_app.config
    result = {}

    # IMAP test
    imap_host = cfg.get('MAIL_IMAP_HOST', '?')
    imap_port = cfg.get('MAIL_IMAP_PORT', 993)
    imap_user, imap_pass = _user_mail_creds()
    pass_source = 'пользователь' if (current_user.mail_user and current_user.mail_password) else (
        'глобальный (пароль не задан у пользователя)' if current_user.mail_user else 'глобальный'
    )
    try:
        conn = _imap_connect()
        _, folders_data = conn.list()
        folder_names = []
        for f in (folders_data or []):
            if isinstance(f, bytes):
                decoded = f.decode('utf-8', errors='replace')
                m = re.search(r'"([^"]+)"\s*$|(\S+)\s*$', decoded)
                if m:
                    folder_names.append(m.group(1) or m.group(2))
        # Test inbox folder
        inbox_folder = cfg.get('MAIL_INBOX_FOLDER', 'info.kf')
        st, _ = conn.select(f'"{inbox_folder}"')
        inbox_count = 0
        if st == 'OK':
            _, sdata = conn.uid('search', None, 'ALL')
            inbox_count = len(sdata[0].split()) if sdata and sdata[0] else 0
        conn.logout()
        result['imap'] = {
            'ok': True,
            'host': f'{imap_host}:{imap_port}',
            'user': imap_user,
            'pass_source': pass_source,
            'folders': folder_names[:30],
            'inbox_folder': inbox_folder,
            'inbox_folder_ok': st == 'OK',
            'inbox_count': inbox_count,
        }
    except Exception as e:
        result['imap'] = {
            'ok': False,
            'host': f'{imap_host}:{imap_port}',
            'user': imap_user,
            'pass_source': pass_source,
            'error': str(e),
        }

    # SMTP test
    smtp_host = cfg.get('MAIL_SMTP_HOST', 'mail.bmstu.ru')
    smtp_port = cfg.get('MAIL_SMTP_PORT', 465)
    smtp_mode = cfg.get('MAIL_SMTP_MODE', 'ssl')
    try:
        ctx = _ssl_ctx()
        if smtp_mode == 'starttls':
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=10)
        smtp_user, smtp_pass = _user_mail_creds()
        with server:
            server.login(smtp_user, smtp_pass)
        result['smtp'] = {'ok': True, 'mode': smtp_mode, 'host': smtp_host, 'port': smtp_port}
    except Exception as e:
        result['smtp'] = {
            'ok': False,
            'error': str(e),
            'mode': smtp_mode,
            'host': smtp_host,
            'port': smtp_port,
        }

    # Return HTML for browser-friendly view
    def row(label, val, ok=None):
        color = '' if ok is None else (' style="color:green"' if ok else ' style="color:red"')
        return f'<tr><td style="padding:4px 12px;opacity:.6">{label}</td><td{color}>{val}</td></tr>'

    imap = result['imap']
    smtp = result['smtp']
    imap_rows = row('Хост', imap['host']) + row('Логин', imap['user']) + row('Пароль (источник)', imap['pass_source'])
    if imap['ok']:
        imap_rows += row('Статус', '✓ OK', True)
        imap_rows += row('Папки', ', '.join(imap['folders']))
        imap_rows += row('Папка входящих', imap['inbox_folder'], imap['inbox_folder_ok'])
        imap_rows += row('Писем в папке', imap['inbox_count'])
    else:
        imap_rows += row('Статус', '✗ Ошибка: ' + imap['error'], False)

    smtp_rows = row('Хост', smtp['host']) + row('Режим', smtp['mode']) + row('Порт', smtp['port'])
    if smtp['ok']:
        smtp_rows += row('Статус', '✓ OK', True)
    else:
        smtp_rows += row('Статус', '✗ Ошибка: ' + smtp['error'], False)

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Mail Diagnostics</title>
<style>body{{font-family:monospace;padding:20px;max-width:800px}}
h2{{margin-top:20px}} table{{border-collapse:collapse;width:100%}}
td{{border-bottom:1px solid #eee;padding:6px 12px}}
</style></head><body>
<h1>Mail Diagnostics</h1>
<h2>IMAP</h2><table>{imap_rows}</table>
<h2>SMTP</h2><table>{smtp_rows}</table>
<p style="margin-top:20px;opacity:.5">
  <a href="/mail">← Назад к почте</a>
</p>
</body></html>'''
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
